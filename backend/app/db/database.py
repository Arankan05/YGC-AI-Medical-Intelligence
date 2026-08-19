import os
from pathlib import Path
from typing import Any, Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker, Session
# Explicitly load .env from backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)

def _get_database_url() -> str:
    """
    Retrieve and format PostgreSQL connection URL from environment variables.
    Configured for SQLAlchemy 2.0 with the psycopg (v3) driver using robust URL parsing.
    """
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url or not raw_url.strip():
        raise ValueError(
            "DATABASE_URL environment variable is missing or empty. "
            "Please ensure it is defined in backend/.env."
        )

    url_str = raw_url.strip()

    # SQLite compatibility for testing
    if url_str.startswith("sqlite"):
        return url_str

    # Normalize legacy postgres:// scheme to postgresql://
    if url_str.startswith("postgres://"):
        url_str = "postgresql://" + url_str[len("postgres://"):]

    # Specify psycopg (v3) driver for SQLAlchemy
    if url_str.startswith("postgresql://"):
        url_str = "postgresql+psycopg://" + url_str[len("postgresql://"):]

    # Parse URL robustly using SQLAlchemy URL utilities
    parsed_url = make_url(url_str)

    # Ensure sslmode=require parameter is present for non-SQLite PostgreSQL connections
    query_dict = dict(parsed_url.query)
    if "sslmode" not in query_dict:
        query_dict["sslmode"] = "require"
        parsed_url = parsed_url.set(query=query_dict)

    return parsed_url.render_as_string(hide_password=False)


# Retrieve sanitized database URL
DATABASE_URL = _get_database_url()

# SQLAlchemy Engine
# Configure connection pool settings for PostgreSQL/Supabase while preserving SQLite compatibility
is_sqlite = DATABASE_URL.startswith("sqlite")

engine_kwargs: dict[str, Any] = {
    "pool_pre_ping": True,
}

if not is_sqlite:
    engine_kwargs.update(
        {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 300,
        }
    )

engine = create_engine(
    DATABASE_URL,
    **engine_kwargs,
)

# Session factory for creating database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative Base class for future SQLAlchemy models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a SQLAlchemy session.
    Ensures that the database session is always closed after request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
