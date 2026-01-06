"""Database session management.

Provides session factory for SQLite database access.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mirage.db.schema import Base

# Default database path
DEFAULT_DB_PATH = Path("data/mirage.db")


def get_engine(db_path: Path | None = None):
    """Get SQLAlchemy engine for the database.

    Args:
        db_path: Path to SQLite database file. Defaults to data/mirage.db.

    Returns:
        SQLAlchemy engine instance.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return create_engine(f"sqlite:///{db_path}", echo=False)


def get_session(db_path: Path | None = None) -> Session:
    """Get a database session.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        SQLAlchemy Session instance.
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def init_db(db_path: Path | None = None) -> None:
    """Initialize database schema.

    Args:
        db_path: Path to SQLite database file.
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
