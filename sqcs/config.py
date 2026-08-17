import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_CONFIG_ERROR = (
    "Neon PostgreSQL connection is missing on Vercel. "
    "Set DATABASE_URL (or POSTGRES_URL / POSTGRES_PRISMA_URL) in the "
    "Vercel project's Environment Variables, then redeploy."
)


def _env(name: str, default: str = "") -> str:
    """
    os.getenv(name, default) only falls back to `default` when the var
    is completely unset. A var set to "" (blank -- easy to do by
    accident in a dashboard's env var UI) still comes back as "" and
    silently skips the default. That's exactly what took down every
    route here: MAX_CONTENT_MB="" made float("") raise at import time.
    This treats unset AND blank/whitespace-only the same way.
    """
    val = os.getenv(name)
    if val is None or val.strip() == "":
        return default
    return val.strip()


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        # Malformed value (e.g. "12mb" instead of "12") -- never let a
        # bad env var take the whole app down. Fall back and move on.
        return default


def _raw_database_url() -> str:
    return (
        _env("DATABASE_URL")
        or _env("DATABASE_URL_POSTGRES_URL")
        or _env("POSTGRES_URL")
        or _env("POSTGRES_PRISMA_URL")
    )


def _normalize(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def database_url():
    """
    Resolve the DB connection string. IMPORTANT: this must never raise.

    A raise here previously killed the whole Vercel function at import
    time -- before Flask, the blueprint, or even /health existed -- so
    every single route (including static assets and the health check)
    returned a raw traceback instead of a diagnosable error.

    Returns:
        (url_or_None, configured: bool)
    """
    url = _normalize(_raw_database_url())
    if url:
        return url, True
    if _env("VERCEL"):
        # No Postgres URL on Vercel: don't fall back to SQLite (it's
        # ephemeral/read-only there), and don't raise. The app will
        # boot in a degraded state; DB-dependent routes return a
        # clean 503 with DB_CONFIG_ERROR instead of a stack trace.
        return None, False
    # Local dev with nothing set: SQLite fallback is fine.
    return f"sqlite:///{BASE_DIR / 'instance' / 'sqcs.db'}", True


class Config:
    SECRET_KEY = _env("SECRET_KEY", "dev-only-change-me")

    _resolved_url, DB_CONFIGURED = database_url()
    # When no real DB is configured, point SQLAlchemy at a harmless
    # in-memory SQLite URI just so init_app() doesn't itself fail.
    # No queries ever run against it -- before_request blocks them
    # whenever DB_CONFIGURED is False (see sqcs/__init__.py).
    SQLALCHEMY_DATABASE_URI = _resolved_url or "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    MAX_CONTENT_LENGTH = int(_env_float("MAX_CONTENT_MB", 12.0) * 1024 * 1024)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env("SESSION_COOKIE_SECURE", "false").lower() == "true"

    REMEMBER_COOKIE_HTTPONLY = True

