def _boot():
    """
    Build the real app, falling back to a minimal error-reporting app if
    anything goes wrong. Wrapped in a function (rather than a bare
    module-level try/except) so the final `app = _boot()` below is a
    single, unindented, top-level assignment -- Vercel's Python builder
    statically scans this file for a top-level "app" and fails the whole
    build if it can't find one at column 0, regardless of what actually
    happens at runtime.
    """
    try:
        from sqcs import create_app
        return create_app()
    except Exception as exc:  # noqa: BLE001 - last-resort safety net
        # create_app() is written to degrade gracefully (see
        # sqcs/__init__.py and sqcs/config.py) rather than raise, but if
        # some future change ever reintroduces an import-time crash,
        # fall back to reporting the error instead of taking down every
        # route on the deployment with a raw traceback.
        from flask import Flask, jsonify

        detail = str(exc)
        fallback = Flask(__name__)

        @fallback.route("/", defaults={"_path": ""})
        @fallback.route("/<path:_path>")
        def _boot_failure(_path):
            return jsonify(error="app_failed_to_start", detail=detail), 500

        return fallback


app = _boot()
