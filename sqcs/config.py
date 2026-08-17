import os
from pathlib import Path
from dotenv import load_dotenv


# ============================================================
# BASE PATH / ENVIRONMENT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env when running locally.
# Vercel environment variables are provided by the platform.
load_dotenv(BASE_DIR / ".env")


# ============================================================
# DATABASE ERROR
# ============================================================

DB_CONFIG_ERROR = (
    "Neon PostgreSQL connection is missing on Vercel. "
    "Set DATABASE_URL, DATABASE_URL_POOLING, or "
    "DATABASE_URL_UNPOOLED in the Vercel project's "
    "Environment Variables, then redeploy."
)


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

def _env(name: str, default: str = "") -> str:
    """
    Safely read an environment variable.

    Treats all of these as missing:
        - variable does not exist
        - empty string
        - whitespace-only value

    This prevents errors such as:

        float("")
        int("")
        invalid database URL
    """
    value = os.getenv(name)

    if value is None:
        return default

    value = value.strip()

    if not value:
        return default

    return value


def _env_float(name: str, default: float) -> float:
    """
    Safely parse a floating-point environment variable.

    Invalid or empty values fall back to the supplied default.
    """
    raw = _env(name)

    if not raw:
        return default

    try:
        value = float(raw)

        # Protect against NaN / infinity.
        if not value == value:
            return default

        if value in (float("inf"), float("-inf")):
            return default

        return value

    except (TypeError, ValueError):
        return default


def _is_vercel() -> bool:
    """
    Detect Vercel execution.
    """
    return bool(_env("VERCEL"))


# ============================================================
# DATABASE URL RESOLUTION
# ============================================================

def _raw_database_url() -> str:
    """
    Find the PostgreSQL connection URL.

    Priority:

        1. DATABASE_URL
        2. DATABASE_URL_POOLING
        3. DATABASE_URL_UNPOOLED
        4. DATABASE_URL_POSTGRES_URL
        5. POSTGRES_URL
        6. POSTGRES_PRISMA_URL

    The first non-empty value wins.

    This supports both manually configured Neon variables and
    variables created automatically by the Vercel Neon integration.
    """

    candidates = (
        "DATABASE_URL",
        "DATABASE_URL_POOLING",
        "DATABASE_URL_UNPOOLED",
        "DATABASE_URL_POSTGRES_URL",
        "POSTGRES_URL",
        "POSTGRES_PRISMA_URL",
    )

    for name in candidates:
        value = _env(name)

        if value:
            return value

    return ""


# ============================================================
# DATABASE URL NORMALIZATION
# ============================================================

def _normalize(url: str) -> str:
    """
    Normalize PostgreSQL URLs for psycopg/SQLAlchemy.

    Supported:

        postgres://...
        postgresql://...
        postgresql+psycopg://...

    SQLite URLs are returned unchanged for local development.
    """

    url = (url or "").strip()

    if not url:
        return ""

    # Already using the SQLAlchemy psycopg dialect.
    if url.startswith("postgresql+psycopg://"):
        return url

    # Standard PostgreSQL scheme.
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]

    # Legacy PostgreSQL scheme.
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]

    # Local SQLite fallback.
    if url.startswith("sqlite://"):
        return url

    # Preserve any other explicitly supplied URL.
    return url


# ============================================================
# DATABASE URL VALIDATION
# ============================================================

def _is_postgres_url(url: str) -> bool:
    """
    Determine whether a URL is PostgreSQL.
    """

    if not url:
        return False

    return url.startswith(
        (
            "postgresql://",
            "postgres://",
            "postgresql+psycopg://",
        )
    )


def _is_local_database_url(url: str) -> bool:
    """
    Detect accidental localhost PostgreSQL configuration.

    This is particularly important on Vercel because there is no
    local PostgreSQL server available at:

        /var/run/postgresql
        localhost
        127.0.0.1
    """

    if not url:
        return False

    lowered = url.lower()

    local_hosts = (
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "/var/run/postgresql",
    )

    return any(host in lowered for host in local_hosts)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

def database_url():
    """
    Resolve the database connection.

    Returns:

        (url, configured)

    Vercel:
        - PostgreSQL is required.
        - SQLite is NEVER used as production storage.
        - Missing/invalid DB configuration returns:
              (None, False)

    Local development:
        - PostgreSQL is used when configured.
        - Otherwise SQLite is allowed.
    """

    raw_url = _raw_database_url()

    if raw_url:
        normalized = _normalize(raw_url)

        # Never allow accidental localhost PostgreSQL on Vercel.
        if _is_vercel() and _is_local_database_url(normalized):
            return None, False

        # On Vercel, require an actual PostgreSQL connection.
        if _is_vercel() and not _is_postgres_url(normalized):
            return None, False

        return normalized, True

    # --------------------------------------------------------
    # VERCEL
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # Never fall back to SQLite on Vercel.
    #
    # Vercel serverless storage is ephemeral and is not suitable
    # for persistent application data.
    #
    if _is_vercel():
        return None, False

    # --------------------------------------------------------
    # LOCAL DEVELOPMENT
    # --------------------------------------------------------

    sqlite_dir = BASE_DIR / "instance"
    sqlite_path = sqlite_dir / "sqcs.db"

    return f"sqlite:///{sqlite_path}", True


# ============================================================
# FLASK CONFIGURATION
# ============================================================

class Config:
    """
    Main Flask application configuration.
    """

    # ========================================================
    # SECURITY
    # ========================================================

    SECRET_KEY = _env(
        "SECRET_KEY",
        "dev-only-change-me",
    )

    # ========================================================
    # DATABASE
    # ========================================================

    _resolved_url, DB_CONFIGURED = database_url()

    # If DB is missing on Vercel, SQLAlchemy still needs a harmless
    # URI so db.init_app() can complete.
    #
    # The application request guard is responsible for preventing
    # database-dependent requests when DB_CONFIGURED is False.
    if _resolved_url:
        SQLALCHEMY_DATABASE_URI = _resolved_url
    elif _is_vercel():
        # Never instantiate SQLite on Vercel. This unreachable placeholder
        # only satisfies Flask-SQLAlchemy initialization; every protected
        # request is blocked by create_app() when DB_CONFIGURED is False.
        SQLALCHEMY_DATABASE_URI = (
            "postgresql+psycopg://disabled:disabled@127.0.0.1:5432/disabled"
        )
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{BASE_DIR / 'instance' / 'sqcs.db'}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ========================================================
    # SQLALCHEMY ENGINE
    # ========================================================

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # ========================================================
    # REQUEST SIZE
    # ========================================================

    # Default: 12 MB
    #
    # Handles:
    #
    #   MAX_CONTENT_MB=""
    #
    # safely without crashing application startup.
    max_content_mb = _env_float(
        "MAX_CONTENT_MB",
        12.0,
    )

    # Prevent invalid values such as:
    #
    #   MAX_CONTENT_MB=-5
    #
    # from creating an invalid MAX_CONTENT_LENGTH.
    if max_content_mb <= 0:
        max_content_mb = 12.0

    MAX_CONTENT_LENGTH = int(
        max_content_mb * 1024 * 1024
    )

    # ========================================================
    # SESSION COOKIE
    # ========================================================

    SESSION_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SAMESITE = "Lax"

    SESSION_COOKIE_SECURE = (
        _env(
            "SESSION_COOKIE_SECURE",
            "true" if _is_vercel() else "false",
        ).lower()
        == "true"
    )

    # ========================================================
    # REMEMBER-ME COOKIE
    # ========================================================

    REMEMBER_COOKIE_HTTPONLY = True

    REMEMBER_COOKIE_SAMESITE = "Lax"

    REMEMBER_COOKIE_SECURE = (
        _env(
            "REMEMBER_COOKIE_SECURE",
            "true" if _is_vercel() else "false",
        ).lower()
        == "true"
    )

    # ========================================================
    # OPTIONAL APPLICATION SETTINGS
    # ========================================================

    APP_ENV = _env(
        "APP_ENV",
        "production" if _is_vercel() else "development",
    )

    DEBUG = (
        _env("FLASK_DEBUG", "false").lower()
        == "true"
    )

    # ========================================================
    # DATABASE CONNECTION STATUS
    # ========================================================

    DATABASE_URL_CONFIGURED = bool(
        _resolved_url
        and DB_CONFIGURED
    )

    # Useful for diagnostics.
    DATABASE_TYPE = (
        "postgresql"
        if _is_postgres_url(_resolved_url or "")
        else "sqlite"
        if (_resolved_url or "").startswith("sqlite://")
        else "none"
    )


# ============================================================
# EXPORT HELPERS
# ============================================================

__all__ = [
    "BASE_DIR",
    "Config",
    "DB_CONFIG_ERROR",
    "database_url",
]
