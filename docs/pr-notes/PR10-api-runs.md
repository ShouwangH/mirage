# PR10: Run Detail Endpoint + Artifact Serving

## Summary

Adds the run detail API endpoint and static file serving for artifacts.

## Changes

### New Files

- `src/mirage/api/routes/runs.py` - GET /api/runs/{run_id} endpoint
- `tests/test_api_runs.py` - 10 API endpoint tests

### Modified Files

- `src/mirage/api/app.py` - Added runs router and artifact static file serving

## API Endpoints

### GET /api/runs/{run_id}

Returns a `RunDetail` containing:
- `run_id` - Run identifier
- `experiment_id` - Parent experiment ID
- `item_id` - Dataset item ID
- `variant_key` - Variant identifier
- `spec_hash` - Generation spec hash
- `status` - Run status (queued/running/succeeded/failed)
- `output_canon_uri` - Canonical output video URI
- `output_sha256` - Output file hash
- `metrics` - MetricBundleV1 if computed
- `status_badge` - pass/flagged/reject from metrics
- `reasons` - List of flag/reject reasons

### GET /artifacts/{path}

Static file serving for artifact files:
- Serves files from `MIRAGE_ARTIFACTS_DIR` environment variable (default: `./artifacts`)
- Returns 404 if file or directory doesn't exist

## Design Decisions

### Artifact Directory Configuration

Uses `MIRAGE_ARTIFACTS_DIR` environment variable to configure the artifacts directory:
- Allows flexibility for different deployment environments
- Defaults to `./artifacts` for local development
- Gracefully handles missing directory with 404 fallback

### Code Reuse

The `_build_run_detail` helper mirrors the one in `experiments.py`. Kept separate to:
1. Allow independent evolution of single-run vs. list-run responses
2. Avoid circular imports between route modules

## Architecture Compliance

Per ARCHITECTURE.md boundary A:
- ✅ Validates inputs (run_id path parameter)
- ✅ Reads DB (queries Run, MetricResult)
- ✅ Returns payloads for UI (RunDetail Pydantic model)
- ✅ Serves static files (artifact videos)
- ✅ Forbidden: provider calls, ffmpeg work, metric computation

## Test Coverage

10 tests covering:
- 200/404 response codes
- Response schema shape validation
- Correct field values
- Metrics inclusion when available
- Status badge extraction
- Artifact endpoint existence
