# PR09: FastAPI App + Experiments Endpoint

## Summary

Implements the FastAPI application layer with the experiment overview endpoint per ARCHITECTURE.md boundary A (api layer).

## Changes

### New Files

- `src/mirage/api/__init__.py` - API module package
- `src/mirage/api/app.py` - FastAPI application factory with dependency injection
- `src/mirage/api/routes/__init__.py` - Routes package
- `src/mirage/api/routes/experiments.py` - GET /api/experiments/{id} endpoint
- `tests/test_api_experiments.py` - 13 API endpoint tests

### Dependencies Added

- `fastapi>=0.100.0` - Web framework
- `uvicorn>=0.20.0` - ASGI server
- `httpx>=0.24.0` - HTTP client for TestClient

## API Endpoint

### GET /api/experiments/{experiment_id}

Returns an `ExperimentOverview` containing:
- `experiment_id` - Experiment identifier
- `status` - Experiment status (draft/running/complete)
- `generation_spec` - Full generation spec details
- `dataset_item` - Dataset item details
- `runs` - List of runs with metrics and status badges
- `human_summary` - Human evaluation summary (null for now, PR12)

### GET /health

Health check endpoint returning `{"status": "ok"}`.

## Design Decisions

### Application Factory Pattern

Used `create_app()` factory function to allow:
1. Test configuration with in-memory databases
2. Future configuration options (db_path, etc.)
3. Clean dependency injection setup

### Dependency Injection for Database Sessions

Used FastAPI's `Depends()` with a generator function for session management:
```python
def get_db_session() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()
```

This allows tests to override with `app.dependency_overrides[get_db_session]`.

### SQLite In-Memory Testing with StaticPool

For testing, SQLite in-memory databases require special handling:
- `StaticPool` ensures the same connection is reused
- `check_same_thread=False` allows cross-thread access
- This prevents "no such table" errors when TestClient uses different threads

```python
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
```

## Architecture Compliance

Per ARCHITECTURE.md boundary A:
- ✅ Validates inputs (experiment_id path parameter)
- ✅ Reads DB (queries Experiment, GenerationSpec, Run, MetricResult)
- ✅ Returns payloads for UI (ExperimentOverview Pydantic model)
- ✅ Forbidden: provider calls, ffmpeg work, metric computation

## Test Coverage

13 tests covering:
- 200/404 response codes
- Response schema shape validation
- Correct field values
- Metrics inclusion when available
- Health endpoint functionality

## Running the API

```bash
# Development server
uvicorn mirage.api.app:app --reload

# Or programmatically
from mirage.api.app import create_app
app = create_app()
```
