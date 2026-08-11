import os
from pathlib import Path
from typing import Generator
from urllib.parse import quote_plus, unquote

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Explicitly load .env from backend directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)


def _get_database_url() -> str:
    """
    Retrieve and format PostgreSQL connection URL from environment variables.
    Configured for SQLAlchemy 2.0 with the psycopg (v3) driver.
    """
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url or not raw_url.strip():
        raise ValueError(
            "DATABASE_URL environment variable is missing or empty. "
            "Please ensure it is defined in backend/.env."
        )

    url = raw_url.strip()

    # Normalize legacy postgres:// scheme to postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # Specify psycopg (v3) driver for SQLAlchemy
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]

    # Handle unencoded special characters (e.g. '@') in passwords safely
    if url.count("@") > 1:
        scheme_and_auth, host_and_db = url.rsplit("@", 1)
        if "://" in scheme_and_auth:
            scheme, auth = scheme_and_auth.split("://", 1)
            if ":" in auth:
                username, password = auth.split(":", 1)
                encoded_password = quote_plus(unquote(password))
                url = f"{scheme}://{username}:{encoded_password}@{host_and_db}"

    return url


# Retrieve sanitized database URL
DATABASE_URL = _get_database_url()

# SQLAlchemy Engine
# pool_pre_ping enables automatic reconnection verification for pooled connections
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
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
