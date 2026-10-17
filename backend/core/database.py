"""SQLAlchemy engine/session setup. Works with SQLite (dev) or Postgres (prod)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.core.config import settings


def _normalize(url: str) -> str:
    """
    Pin Postgres URLs to the psycopg2 driver. SQLAlchemy 2.1 resolves a bare
    'postgresql://' to psycopg (v3), which we don't bundle; hosts like Railway
    also hand out the legacy 'postgres://' scheme. Rewrite both to
    'postgresql+psycopg2://' so the bundled psycopg2-binary is used.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize(settings.DATABASE_URL)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    # SQLite needs this to be used across FastAPI's threadpool.
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
