# PR12: Human Eval - Rating Submission + Aggregation

## Summary

Implements rating submission and win rate aggregation for human evaluation, plus naming convention improvements.

## Changes

### New Files

- `src/mirage/eval/ratings.py` - Rating submission logic
- `src/mirage/aggregation/__init__.py` - Aggregation module package
- `src/mirage/aggregation/summary.py` - Win rate calculation
- `src/mirage/api/routes/ratings.py` - Rating API endpoints
- `tests/test_api_ratings.py` - 11 API endpoint tests

### Renamed Files (Naming Convention Improvement)

- `src/mirage/metrics/tier0.py` → `src/mirage/metrics/video_quality.py`
- `src/mirage/metrics/tier1.py` → `src/mirage/metrics/face_metrics.py`
- `tests/test_metrics_tier0.py` → `tests/test_video_quality.py`
- `tests/test_metrics_tier1.py` → `tests/test_face_metrics.py`
- Function `compute_tier0_metrics` → `compute_video_quality_metrics`
- Function `compute_tier1_metrics` → `compute_face_metrics`

### Modified Files

- `src/mirage/api/app.py` - Added ratings router
- `src/mirage/metrics/bundle.py` - Updated imports for renamed files
- `CLAUDE.md` - Added section 9: naming conventions

## API Endpoints

### POST /api/ratings

Submit a human rating for a pairwise comparison task.

Request body (RatingSubmission):
```json
{
  "task_id": "task-001",
  "rater_id": "rater-001",
  "choice_realism": "left",
  "choice_lipsync": "right",
  "choice_targetmatch": null,
  "notes": null
}
```

Response:
```json
{
  "rating_id": "uuid",
  "task_id": "task-001"
}
```

### GET /api/experiments/{experiment_id}/summary

Get human evaluation summary with win rates.

Response (HumanSummary):
```json
{
  "win_rates": {
    "variant-a": 0.75,
    "variant-b": 0.25
  },
  "recommended_pick": "variant-a",
  "total_comparisons": 5
}
```

## Win Rate Calculation

Win rates are calculated from pairwise comparison ratings:

1. Each rating has two choices: `choice_realism` and `choice_lipsync`
2. Each choice can be "left", "right", "tie", or "skip"
3. Scoring:
   - Win (left/right): 0.5 points to winner
   - Tie: 0.25 points to each
   - Skip: 0 points
4. Win rate = total points / (2 * total_comparisons)

The `flip` flag is accounted for when mapping presented choices back to canonical variants.

## Naming Convention Updates

Added naming conventions to CLAUDE.md (section 9):
- Files should be named for what they contain, not implementation details
- Avoid arbitrary labels like "tier0", "v1", "update1"
- When encountering poor names: identify 3-5 alternatives, choose the best

Applied to metric files:
- `tier0.py` → `video_quality.py` (describes what it measures)
- `tier1.py` → `face_metrics.py` (describes the domain)

## Architecture Compliance

Per ARCHITECTURE.md:
- **eval module**: Rating storage and task status updates
- **aggregation module** (boundary E): Reads DB, produces summaries
- **api layer** (boundary A): Validates inputs, returns payloads

## Test Coverage

11 tests covering:
- 201/404 response codes for rating submission
- Rating record creation
- Task status update to "done"
- Append-only ratings (multiple ratings allowed)
- Human summary shape and win rate calculation
- Recommended pick selection
