# PR15: Minimal Web UI - Pairwise Eval Overlay

## Summary

Implements the human evaluation UI for pairwise video comparison, allowing raters to compare variants side-by-side and submit ratings on realism and lip sync quality.

## Changes

### New Files

- `ui/components/EvalOverlay.tsx` - Side-by-side video comparison overlay
- `ui/components/EvalOverlay.module.css` - Styling for the overlay
- `ui/pages/eval/[id].tsx` - Evaluation workflow page
- `ui/pages/eval/Eval.module.css` - Styling for the eval page

### Modified Files

- `ui/lib/api.ts` - Added `submitRating()` and `getTask()` functions
- `ui/pages/experiment/[id].tsx` - Added "Start Evaluation" button
- `ui/styles/Experiment.module.css` - Added styles for eval button

## Architecture

### Component Structure

```
EvalPage (/eval/[experiment_id])
├── Header with experiment info
├── Task creation UI (if no tasks exist)
├── EvalOverlay (when task is active)
│   ├── Side-by-side video players
│   ├── Playback controls (Play Both, Pause, Restart)
│   ├── Rating criteria (Realism, Lip Sync)
│   └── Submit button
└── Results summary (when all tasks complete)
```

### Data Flow

1. Page loads experiment and checks for open tasks
2. If no tasks, user can create pairwise comparison tasks
3. Tasks are presented one at a time with randomized left/right assignment
4. User rates each criterion and submits
5. After all tasks, summary shows win rates and recommended pick

### API Integration

Uses existing endpoints:
- `POST /api/experiments/{id}/tasks` - Create pairwise tasks
- `GET /api/experiments/{id}/tasks/next` - Get next open task
- `POST /api/ratings` - Submit rating
- `GET /api/experiments/{id}/summary` - Get aggregated results

## Key Decisions

1. **Anonymous raters**: For MVP, rater IDs are auto-generated (`anon_${timestamp}`). Production would integrate with auth.

2. **Synchronized playback**: Videos can be played/paused together for fair comparison, but also have individual controls.

3. **Simple rating UI**: Two required criteria (Realism, Lip Sync) with options: Left wins, Tie, Right wins, Skip.

4. **Immediate feedback**: After each submission, automatically loads next task or shows completion summary.

## Testing

Manual testing:
```bash
# Start API
cd /path/to/mirage
source .venv/bin/activate
PYTHONPATH=src uvicorn mirage.api.app:app --reload

# Start UI
cd ui
npm run dev

# Test flow:
# 1. Go to http://localhost:3000/experiment/demo
# 2. Click "Start Evaluation"
# 3. Click "Create Comparison Tasks"
# 4. Rate each pair
# 5. View results summary
```

## Commands Run

```bash
# Format
cd ui && npm run lint

# Build check
npm run build
```
