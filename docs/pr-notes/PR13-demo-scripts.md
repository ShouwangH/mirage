# PR13: Demo Seeding Script + Smoke Test

## Summary

This PR adds one-command demo setup scripts that create a complete demo experiment
with cached artifacts, runs, and computed metrics.

## Changes

### New Files

- `scripts/seed_demo.py` - Seeds demo experiment with artifacts and metrics
- `scripts/smoke_demo.py` - Validates demo experiment is correctly set up

### Assets Created

The seed script creates:
- `demo_assets/demo_source.mp4` - 2-second test pattern video with audio
- `demo_assets/demo_audio.wav` - 2-second 440Hz sine wave audio
- `demo.db` - SQLite database with seeded experiment
- `artifacts/runs/{run_id}/` - Generated and normalized artifacts

## Usage

```bash
# Seed the demo (creates assets, database, runs, computes metrics)
python scripts/seed_demo.py

# Validate the demo is correctly set up
python scripts/smoke_demo.py
```

## Demo Experiment Structure

The seed script creates:

1. **DatasetItem** (`demo_item`)
   - Source video: `demo_assets/demo_source.mp4`
   - Audio: `demo_assets/demo_audio.wav`

2. **GenerationSpec** (`demo_spec`)
   - Provider: `mock`
   - Model: `mock-v1`
   - Prompt: "Generate a talking head video."

3. **Experiment** (`demo`)
   - Links spec to dataset item
   - Status: complete (after processing)

4. **Runs** (3 variants)
   - `seed=42`
   - `seed=123`
   - `seed=456`

Each run goes through the full pipeline:
1. Provider generation (mock)
2. Video normalization
3. Metrics computation (MetricBundleV1)

## Smoke Test Checks

The smoke test validates:

1. Demo assets exist (video + audio)
2. Demo database exists
3. Experiment exists and has correct status
4. All runs succeeded
5. MetricBundleV1 computed with all required keys
6. Status badge is valid (pass/flagged/reject)

## Design Decisions

### Idempotency

Both scripts are idempotent:
- `seed_demo.py` skips if experiment already exists
- `smoke_demo.py` only reads, never writes

### Graceful Degradation

- If ffmpeg is unavailable, creates minimal placeholder files
- Smoke test reports specific failure reasons

### Database Location

Demo uses `demo.db` in project root (not `data/mirage.db`) to keep
demo data separate from development data.

## Testing

```bash
# Run demo-related tests
python -m pytest tests/test_demo.py -v

# Manual verification
python scripts/seed_demo.py
python scripts/smoke_demo.py
```

## Dependencies

- ffmpeg (for creating demo video/audio)
- All existing mirage dependencies (sqlalchemy, opencv, mediapipe)
