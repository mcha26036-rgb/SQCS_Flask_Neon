from flask import Flask
from .config import Config
from .extensions import db
from .services import seed_templates, ensure_admin


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
    app.static_folder = 'static'
    db.init_app(app)
    from .routes import bp
    app.register_blueprint(bp)
    with app.app_context():
        from pathlib import Path
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
        db.create_all()
        seed_templates()
        ensure_admin()
    return app
