from flask import Flask, jsonify, request
from .config import Config, DB_CONFIG_ERROR
from .extensions import db

# Paths that must keep working even when the DB isn't configured, so
# the failure is diagnosable instead of a blanket 500/503 on everything.
_ALWAYS_ALLOWED_PATHS = {"/health", "/setup-status", "/favicon.ico"}


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
    app.static_folder = "static"
    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    @app.before_request
    def _guard_missing_db():
        if not app.config.get("DB_CONFIGURED"):
            if request.path in _ALWAYS_ALLOWED_PATHS or request.path.startswith("/static/"):
                return None
            return jsonify(error="database_not_configured", detail=DB_CONFIG_ERROR), 503

    if app.config.get("DB_CONFIGURED"):
        with app.app_context():
            from pathlib import Path
            try:
                Path(app.instance_path).mkdir(parents=True, exist_ok=True)
            except OSError:
                # Read-only filesystem (e.g. Vercel serverless). Only
                # needed for the local SQLite fallback; safe to skip
                # when a real DATABASE_URL (Neon/Postgres) is set.
                pass
            try:
                db.create_all()
                from .services import seed_templates, ensure_admin
                seed_templates()
                ensure_admin()
            except Exception as exc:
                # Don't let a transient DB hiccup at cold start take
                # down every route for the rest of the container's
                # life -- log it and flip to degraded mode so /health
                # reports it clearly instead of the app 500ing forever.
                app.logger.exception("DB init failed: %s", exc)
                app.config["DB_CONFIGURED"] = False

    return app
