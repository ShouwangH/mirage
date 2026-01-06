"""Database session management.

Provides session factory for SQLite database access with proper
thread-safety for FastAPI concurrency.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from mirage.db.schema import Base

# Default database path
DEFAULT_DB_PATH = Path("data/mirage.db")

# Module-level engine cache for connection pooling
_engine_cache: dict[str, Engine] = {}

# Module-level session factory cache
_session_factory_cache: dict[str, sessionmaker] = {}


def get_engine(db_path: Path | None = None) -> Engine:
    """Get SQLAlchemy engine for the database.

    Engines are cached by resolved db_path to enable connection pooling.
    Subsequent calls with the same path return the cached engine.

    Uses StaticPool and check_same_thread=False for SQLite thread-safety
    under FastAPI concurrency.

    Args:
        db_path: Path to SQLite database file. Defaults to data/mirage.db.

    Returns:
        SQLAlchemy engine instance (cached).
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    db_path = Path(db_path)
    cache_key = str(db_path.resolve())

    if cache_key in _engine_cache:
        return _engine_cache[cache_key]

    # Create parent directories only when creating a new engine
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # SQLite thread-safety config for FastAPI concurrency:
    # - check_same_thread=False: Allow multi-threaded access
    # - StaticPool: Single connection shared across threads (safe for SQLite)
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _engine_cache[cache_key] = engine

    return engine


def _get_session_factory(db_path: Path | None = None) -> sessionmaker:
    """Get cached session factory for the database.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        Cached sessionmaker instance.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    db_path = Path(db_path)
    cache_key = str(db_path.resolve())

    if cache_key in _session_factory_cache:
        return _session_factory_cache[cache_key]

    engine = get_engine(db_path)
    factory = sessionmaker(bind=engine)
    _session_factory_cache[cache_key] = factory

    return factory


def get_session(db_path: Path | None = None) -> Session:
    """Get a database session.

    Note: Caller is responsible for closing the session. For automatic
    resource management, use get_db_session() context manager instead.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        SQLAlchemy Session instance.
    """
    factory = _get_session_factory(db_path)
    return factory()


@contextmanager
def get_db_session(db_path: Path | None = None) -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic cleanup.

    Commits on successful exit, rolls back on exception, and always
    closes the session.

    Args:
        db_path: Path to SQLite database file.

    Yields:
        SQLAlchemy Session instance.

    Example:
        with get_db_session() as session:
            session.add(record)
            # Auto-commits on exit, rolls back on exception
    """
    session = get_session(db_path)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(db_path: Path | None = None) -> None:
    """Initialize database schema.

    Call this once during application startup to create tables.

    Args:
        db_path: Path to SQLite database file.
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
