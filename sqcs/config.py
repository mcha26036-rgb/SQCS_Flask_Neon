import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def database_url():
    # Neon / Vercel PostgreSQL connection
    url = (
        os.getenv("DATABASE_URL")
        or os.getenv("DATABASE_URL_POSTGRES_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRES_PRISMA_URL")
        or ""
    ).strip()

    # SQLAlchemy PostgreSQL driver
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]

    if url:
        return url

    # NEVER fall back to SQLite on Vercel
    if os.getenv("VERCEL"):
        raise RuntimeError(
            "Neon PostgreSQL connection is missing on Vercel. "
            "Set DATABASE_URL to the Neon PostgreSQL connection string."
        )

    # SQLite only for local development
    return f"sqlite:///{BASE_DIR / 'instance' / 'sqcs.db'}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    MAX_CONTENT_LENGTH = int(
        float(os.getenv("MAX_CONTENT_MB", "12")) * 1024 * 1024
    )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (
        os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    )

    REMEMBER_COOKIE_HTTPONLY = True
