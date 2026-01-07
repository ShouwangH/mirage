# PR16: Export + Recommended Pick Display

## Summary

Adds export functionality and improved results display for experiments. Users can now download experiment results as JSON and see win rates with a visual bar chart on the experiment overview page.

## Changes

### New Files

- `src/mirage/api/routes/export.py` - Export API endpoint
- `ui/components/Results.tsx` - Results display component with export button
- `ui/components/Results.module.css` - Styling for results component

### Modified Files

- `src/mirage/api/app.py` - Registered export router
- `ui/pages/experiment/[id].tsx` - Integrated Results component, fetch human summary
- `ui/lib/api.ts` - (already had getHumanSummary)

## API Endpoint

### GET /api/experiments/{experiment_id}/export

Returns experiment data as downloadable JSON file.

Response headers:
```
Content-Disposition: attachment; filename="{experiment_id}_export.json"
```

Response body:
```json
{
  "experiment_id": "demo",
  "status": "complete",
  "export_version": "1.0",
  "generation_spec": {
    "provider": "mock",
    "model": "mock-v1",
    "prompt_template": "...",
    "params": {}
  },
  "dataset_item": {
    "item_id": "...",
    "subject_id": "...",
    "source_video_uri": "...",
    "audio_uri": "..."
  },
  "runs": [
    {
      "run_id": "...",
      "variant_key": "seed=42",
      "status": "succeeded",
      "output_sha256": "...",
      "metrics": { ... },
      "status_badge": "pass",
      "reasons": []
    }
  ],
  "human_summary": {
    "win_rates": { "run_id": 0.5, ... },
    "recommended_pick": "run_id",
    "total_comparisons": 3
  }
}
```

## UI Components

### Results Component

Features:
- Export button that triggers JSON download
- Recommended pick highlight with green background
- Visual win rate bars sorted by percentage
- Star indicator for the recommended variant
- Total comparisons count

## Architecture

The Results component is purely presentational - it receives data from the server and renders it. The export functionality opens the API endpoint in a new tab, triggering the browser's download behavior via the Content-Disposition header.

## Testing

Manual testing:
```bash
# Start API
PYTHONPATH=src uvicorn mirage.api.app:app --reload

# Start UI
cd ui && npm run dev

# Test:
# 1. Go to http://localhost:3000/experiment/demo
# 2. Verify Results section shows win rates
# 3. Click "Export Results" button
# 4. Verify JSON file downloads
```

## Commands Run

```bash
# Test export endpoint
curl -s http://localhost:8000/api/experiments/demo/export | python3 -m json.tool

# Verify download header
curl -s -D - http://localhost:8000/api/experiments/demo/export -o /dev/null
```
