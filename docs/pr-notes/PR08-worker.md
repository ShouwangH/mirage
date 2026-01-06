# PR08: Worker Orchestrator

## Summary

Implements the worker orchestrator that processes runs through the complete pipeline: provider generation → normalization → metrics computation.

## Files Changed

- `src/mirage/db/session.py` - Database session management
- `src/mirage/worker/__init__.py` - Package init
- `src/mirage/worker/orchestrator.py` - WorkerOrchestrator implementation
- `tests/test_worker.py` - 14 tests for orchestrator behavior

## Implementation Details

### WorkerOrchestrator

Main class that orchestrates the run processing pipeline:

```python
class WorkerOrchestrator:
    def __init__(self, session: Session, output_dir: Path): ...
    def get_queued_runs(self) -> list[Run]: ...
    def process_run(self, run: Run) -> None: ...
```

### Pipeline Steps

1. **Update status to running** - Sets `run.status = "running"` and `started_at`
2. **Build GenerationInput** - Fetches DatasetItem, Experiment, GenerationSpec from DB
3. **Call provider** - Uses MockProvider, creates ProviderCall record
4. **Normalize video** - Calls `normalize_video()` to create canonical mp4
5. **Compute metrics** - Calls `compute_metrics()`, stores MetricResult
6. **Update success/failure** - Sets final status, `ended_at`, `output_canon_uri`

### Database Session Module

Simple session factory for SQLite:

```python
def get_session(db_path: Path | None = None) -> Session: ...
def get_engine(db_path: Path | None = None): ...
def init_db(db_path: Path | None = None) -> None: ...
```

### Idempotency

- Provider calls tracked via `ProviderCall` table with `provider_idempotency_key`
- Same input produces same provider job (via `compute_provider_idempotency_key`)

### Error Handling

Failed runs:
- Status set to "failed"
- `error_code` = exception class name
- `error_detail` = exception message
- `ended_at` timestamp recorded

## Testing

```bash
pytest tests/test_worker.py -v
```

- 3 tests for interface
- 3 tests for get_queued_runs
- 3 tests for process_run status handling
- 3 tests for pipeline steps (ProviderCall, MetricResult, output_canon_uri)
- 2 tests for timestamps

## Boundary Compliance

Per ARCHITECTURE.md boundary B:
- Worker performs expensive side effects (provider, normalize, metrics)
- Owns retry/idempotency logic
- No UI rendering concerns
- Not a giant "manager" class - delegates to specialized modules

## Verification

```bash
ruff check .
ruff format --check .
pytest tests/ -v
```
