from pathlib import Path

from flask import Flask, jsonify, request

from .config import Config, DB_CONFIG_ERROR
from .extensions import db


_ALWAYS_ALLOWED_PATHS = {"/health", "/setup-status", "/favicon.ico"}


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

    # The package lives under /sqcs. Keep static/template discovery explicit
    # so the same app behaves consistently locally and on Vercel.
    app.static_folder = str(Path(__file__).resolve().parent / "static")
    app.template_folder = str(Path(__file__).resolve().parent / "templates")

    db.init_app(app)

    # Import every model before create_all(). SQLAlchemy only creates tables
    # for models that have already been registered with its metadata.
    from .models import User, Project, ChecklistTemplate, Document, AuditLog  # noqa: F401
    from .managed_documents_model import ManagedDocument  # noqa: F401
    from .routes import bp
    from .managed_documents_routes import managed_bp

    app.register_blueprint(bp)
    app.register_blueprint(managed_bp)

    @app.before_request
    def _guard_missing_db():
        if not app.config.get("DB_CONFIGURED"):
            if request.path in _ALWAYS_ALLOWED_PATHS or request.path.startswith("/static/"):
                return None
            return jsonify(error="database_not_configured", detail=DB_CONFIG_ERROR), 503
        return None

    if app.config.get("DB_CONFIGURED"):
        with app.app_context():
            try:
                Path(app.instance_path).mkdir(parents=True, exist_ok=True)
            except OSError:
                pass

            try:
                db.create_all()
                from .services import seed_templates, ensure_admin
                seed_templates()
                ensure_admin()
            except Exception as exc:
                app.logger.exception("DB init failed: %s", exc)
                # Do not silently turn a real DB error into a misleading
                # working-looking application. The health endpoint remains
                # useful, while protected pages return a clear DB error.
                app.config["DB_CONFIGURED"] = False

    return app
