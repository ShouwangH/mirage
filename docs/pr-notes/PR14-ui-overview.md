# PR14: Minimal Web UI - Experiment Overview

## Summary
Created a Next.js web UI that displays experiment overview with variant cards, video playback, metrics, and status badges.

## Implementation

### Technology Stack
- Next.js 16 with TypeScript
- React 19
- CSS Modules for styling
- Server-side rendering via `getServerSideProps`

### Directory Structure
```
ui/
├── pages/
│   ├── index.tsx              # Redirects to /experiment/demo
│   └── experiment/[id].tsx    # Main experiment overview page
├── components/
│   ├── StatusBadge.tsx        # pass/flagged/reject badge with colors
│   ├── VideoPlayer.tsx        # HTML5 video player
│   ├── MetricsBlock.tsx       # Key metrics display
│   └── VariantCard.tsx        # Full variant card component
├── lib/
│   └── api.ts                 # API client for backend
├── types/
│   └── index.ts               # TypeScript types matching backend
└── styles/
    └── Experiment.module.css  # Page-specific styles
```

### Key Features
1. **Experiment Overview Page** (`/experiment/[id]`)
   - Displays experiment status (draft/running/complete)
   - Shows generation spec (provider, model, prompt)
   - Collapsible source context section
   - Grid of variant cards

2. **Variant Cards**
   - Video playback with HTML5 controls
   - Status badge (pass=green, flagged=orange, reject=red)
   - Reasons listed under badge
   - Key metrics: face present ratio, mouth-audio correlation, A/V delta

3. **Human Evaluation Results** (when available)
   - Recommended pick
   - Win rates per variant
   - Total comparison count

### API Integration
The UI calls these backend endpoints:
- `GET /api/experiments/{id}` - Experiment overview data
- `GET /artifacts/{path}` - Video artifacts

### CORS Configuration
Added CORS middleware to FastAPI (`src/mirage/api/app.py`) to allow requests from:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

## Files Changed

### New Files
- `ui/` directory with full Next.js project
- 15+ new TypeScript/React files

### Modified Files
- `src/mirage/api/app.py` - Added CORS middleware

## Running Locally

```bash
# Terminal 1: Start API
cd /path/to/mirage
source .venv/bin/activate
uvicorn mirage.api.app:app --reload

# Terminal 2: Start UI
cd /path/to/mirage/ui
npm install
npm run dev
# Open http://localhost:3000/experiment/demo
```

## Testing
- Backend tests: All 203 tests pass
- UI tests: Manual verification against running API
- Verified: Video playback, metrics display, status badges

## Future Work (PR15-16)
- PR15: Pairwise evaluation overlay (side-by-side comparison)
- PR16: Export functionality and results display
