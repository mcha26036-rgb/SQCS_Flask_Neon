import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def database_url():
    url = os.getenv('DATABASE_URL', '').strip()
    if url.startswith('postgres://'):
        url = 'postgresql+psycopg://' + url[len('postgres://'):]
    elif url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]
    if url:
        return url
    return f"sqlite:///{BASE_DIR / 'instance' / 'sqcs.db'}"


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-only-change-me')
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    _max_content_mb_raw = (os.getenv('MAX_CONTENT_MB') or '12').strip() or '12'
    try:
        _max_content_mb = float(_max_content_mb_raw)
    except ValueError:
        _max_content_mb = 12.0
    MAX_CONTENT_LENGTH = int(_max_content_mb * 1024 * 1024)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    REMEMBER_COOKIE_HTTPONLY = True
