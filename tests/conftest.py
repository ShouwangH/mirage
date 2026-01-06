"""Shared pytest fixtures for mirage tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mirage.db.schema import Base


@pytest.fixture
def engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a database session for testing."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
