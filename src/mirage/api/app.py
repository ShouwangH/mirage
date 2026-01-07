"""FastAPI application factory.

Per ARCHITECTURE.md boundary A (api layer):
- Validates inputs, reads/writes DB
- Returns payloads for UI
- Forbidden: provider calls, ffmpeg work, metric computation
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from mirage.db.repo import DbSession
from mirage.db.session import get_session


def get_db_session() -> Generator[DbSession, None, None]:
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

    # Add CORS middleware for UI access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # Next.js dev server
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    from mirage.api.routes import experiments, export, ratings, runs, tasks

    app.include_router(experiments.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(ratings.router, prefix="/api")
    app.include_router(export.router, prefix="/api")

    # Mount static files for artifacts
    artifacts_dir = Path(os.environ.get("MIRAGE_ARTIFACTS_DIR", "artifacts"))
    if artifacts_dir.exists():
        app.mount("/artifacts", StaticFiles(directory=str(artifacts_dir)), name="artifacts")
    else:
        # Create a fallback handler for artifacts when directory doesn't exist
        from fastapi import HTTPException

        @app.get("/artifacts/{path:path}")
        def artifacts_not_found(path: str):
            """Return 404 for artifacts when directory not configured."""
            raise HTTPException(status_code=404, detail="Artifact not found")

    # Health check endpoint
    @app.get("/health")
    def health_check():
        """Health check endpoint."""
        return {"status": "ok"}

    return app


# Default app instance
app = create_app()
