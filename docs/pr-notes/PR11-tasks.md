# PR11: Human Eval - Task Generation

## Summary

Implements pairwise comparison task generation for human evaluation with randomization to prevent left/right bias.

## Changes

### New Files

- `src/mirage/eval/__init__.py` - Eval module package
- `src/mirage/eval/tasks.py` - Pairwise task generation logic
- `src/mirage/api/routes/tasks.py` - Task API endpoints
- `tests/test_api_tasks.py` - 13 API endpoint tests

### Modified Files

- `src/mirage/api/app.py` - Added tasks router
- `src/mirage/metrics/tier0.py` - Added timeout error handling for ffprobe

## API Endpoints

### POST /api/experiments/{experiment_id}/tasks

Creates pairwise comparison tasks for all unique pairs of succeeded runs.

Response:
```json
{
  "tasks_created": 3,
  "experiment_id": "exp-001"
}
```

Features:
- Idempotent - calling twice won't create duplicate tasks
- Only creates tasks for `succeeded` runs
- Randomizes left/right presentation to prevent bias

### GET /api/tasks/{task_id}

Returns a `TaskDetail` containing:
- `task_id` - Task identifier
- `experiment_id` - Parent experiment ID
- `left_run_id` / `right_run_id` - Original run IDs (canonical order)
- `presented_left_run_id` / `presented_right_run_id` - Presentation order (may be flipped)
- `flip` - Whether presentation was flipped
- `status` - Task status (open/assigned/done/void)

### GET /api/experiments/{experiment_id}/tasks/next

Returns the next open task for an experiment, or 404 if none available.

## Design Decisions

### Bias Prevention

Each task records:
1. **Canonical order**: `left_run_id` and `right_run_id` are always stored in a deterministic order
2. **Presentation order**: `presented_left_run_id` and `presented_right_run_id` are randomly assigned
3. **Flip flag**: Records whether the presentation was flipped from canonical order

This allows:
- Analysis can use canonical order for consistent aggregation
- UI uses presentation order to prevent evaluator bias
- Flip can be analyzed to verify randomization worked

### Idempotency

Task creation is idempotent:
- Checks existing tasks before creating new ones
- Uses order-independent pair matching (sorted tuple)
- Second call returns `tasks_created: 0` if all pairs exist

### Bug Fix: ffprobe Timeout Handling

Added try/except around ffprobe subprocess call to catch `subprocess.TimeoutExpired` and convert to a clear `RuntimeError` with timeout info and partial output.

## Architecture Compliance

Per ARCHITECTURE.md:
- **eval module**: Task generation with randomization
- **api layer**: Validates inputs, reads/writes DB, returns payloads

## Test Coverage

13 tests covering:
- 201/404 response codes for task creation
- Pairwise task generation correctness
- Task count for n runs (n choose 2 pairs)
- Flip flag recording
- Presentation order matches flip
- Idempotent task creation
- GET task detail
- GET next open task
