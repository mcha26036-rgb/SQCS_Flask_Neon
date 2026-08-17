from sqcs import create_app

try:
    app = create_app()
except Exception as _boot_exc:  # noqa: BLE001 - last-resort safety net
    # create_app() is written to degrade gracefully (see sqcs/__init__.py
    # and sqcs/config.py) rather than raise, but if some future change
    # ever reintroduces an import-time crash, fall back to a minimal app
    # that reports the error instead of taking down every single route
    # on the deployment with a raw traceback.
    from flask import Flask, jsonify

    _detail = str(_boot_exc)

    app = Flask(__name__)

    @app.route("/", defaults={"_path": ""})
    @app.route("/<path:_path>")
    def _boot_failure(_path):
        return jsonify(error="app_failed_to_start", detail=_detail), 500
