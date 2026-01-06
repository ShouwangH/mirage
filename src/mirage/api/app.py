"""FastAPI application factory.

Per ARCHITECTURE.md boundary A (api layer):
- Validates inputs, reads/writes DB
- Returns payloads for UI
- Forbidden: provider calls, ffmpeg work, metric computation
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

from fastapi import FastAPI
from sqlalchemy.orm import Session

from mirage.db.session import get_session


def get_db_session() -> Generator[Session, None, None]:
    """Dependency to get database session.

    Yields:
        Database session that is automatically closed after request.
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def create_app(db_path: Path | None = None) -> FastAPI:
    """Create FastAPI application.

    Args:
        db_path: Optional path to database file.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Mirage API",
        description="Talking-head video evaluation loop",
        version="0.1.0",
    )

    # Include routes
    from mirage.api.routes import experiments

    app.include_router(experiments.router, prefix="/api")

    # Health check endpoint
    @app.get("/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "ok"}

    return app


# Default app instance
app = create_app()
