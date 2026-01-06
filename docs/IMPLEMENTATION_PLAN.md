# IMPLEMENTATION_PLAN.md

> Frozen implementation plan for Mirage MVP.
> Changes to this plan require explicit approval and PRD.md update.

---

## Non-Goals (Explicit)

- Multi-user authentication
- Distributed workers/queues
- Multiple provider integrations (only 1 mock provider for MVP)
- Voice cloning or automatic prompt rewriting
- Public uploads
- Ground truth reconstruction metrics
- Polished production UI (demo quality is sufficient)

---

## Interface Specification (Frozen)

### Pydantic Models (API Responses)

```python
# src/mirage/models/types.py

class GenerationInput(BaseModel):
    provider: str
    model: str
    model_version: str | None
    prompt_template: str
    params: dict
    seed: int
    input_audio_path: Path
    input_audio_sha256: str
    ref_image_path: Path | None
    ref_image_sha256: str | None

class RawArtifact(BaseModel):
    raw_video_path: Path
    provider_job_id: str | None
    cost_usd: float | None
    latency_ms: int | None

class CanonArtifact(BaseModel):
    canon_video_path: Path
    sha256: str
    duration_ms: int

class MetricBundleV1(BaseModel):
    # Tier 0
    decode_ok: bool
    video_duration_ms: int
    audio_duration_ms: int
    av_duration_delta_ms: int
    fps: float
    frame_count: int
    scene_cut_count: int
    freeze_frame_ratio: float
    flicker_score: float
    blur_score: float
    frame_diff_spike_count: int
    # Tier 1
    face_present_ratio: float
    face_bbox_jitter: float
    landmark_jitter: float
    mouth_open_energy: float
    mouth_audio_corr: float
    blink_count: int | None
    blink_rate_hz: float | None
    # Tier 2 (optional)
    lse_d: float | None
    lse_c: float | None
    # Status
    status_badge: Literal["pass", "flagged", "reject"]
    reasons: list[str]

class RunDetail(BaseModel):
    run_id: str
    experiment_id: str
    item_id: str
    variant_key: str
    spec_hash: str
    status: Literal["queued", "running", "succeeded", "failed"]
    output_canon_uri: str | None
    output_sha256: str | None
    metrics: MetricBundleV1 | None
    status_badge: Literal["pass", "flagged", "reject"] | None
    reasons: list[str]

class ExperimentOverview(BaseModel):
    experiment_id: str
    status: Literal["draft", "running", "complete"]
    generation_spec: GenerationSpecDetail
    dataset_item: DatasetItemDetail
    runs: list[RunDetail]
    human_summary: HumanSummary | None

class HumanSummary(BaseModel):
    win_rates: dict[str, float]  # variant_key -> win_rate
    recommended_pick: str | None  # variant_key
    total_comparisons: int

class RatingSubmission(BaseModel):
    task_id: str
    rater_id: str
    choice_realism: Literal["left", "right", "tie", "skip"]
    choice_lipsync: Literal["left", "right", "tie", "skip"]
    choice_targetmatch: Literal["left", "right", "tie", "skip"] | None
    notes: str | None
```

### Function Signatures (Boundary Modules)

```python
# Provider adapter (boundary C)
def generate_variant(input: GenerationInput) -> RawArtifact: ...

# Normalizer (boundary B)
def normalize_video(raw_path: Path, audio_path: Path, output_path: Path) -> CanonArtifact: ...

# Metrics engine (boundary D)
def compute_metrics(canon_path: Path, audio_path: Path) -> MetricBundleV1: ...

# Aggregator (boundary E)
def summarize_experiment(db: Session, experiment_id: str) -> HumanSummary: ...
```

### Module Ownership

| Module | Responsibility | Forbidden |
|--------|----------------|-----------|
| `api/` | HTTP endpoints, validation, DB read/write | Provider calls, ffmpeg, metrics |
| `worker/` | Orchestration, retry logic | UI concerns, giant manager class |
| `providers/` | `generate(input) -> raw` | DB writes, metrics, UI |
| `metrics/` | Pure computations | Provider calls, DB writes |
| `normalize/` | ffmpeg transcoding | DB writes, metrics |
| `aggregation/` | Win rates, recommendations | Mutations, provider calls |
| `db/` | Schema, sessions, queries | Business logic |

---

## PR Sequence

### PR00: Initial documentation setup
- **Scope**: Verify existing documentation, add implementation plan
- **Files**: `docs/IMPLEMENTATION_PLAN.md`, `docs/pr-notes/PR00-docs-setup.md`
- **Demo impact**: None (documentation only)
- **Tests**: N/A (documentation only)
- **Docs**: PR notes explaining repo structure
- **Interfaces touched**: No

### PR01: Project scaffolding + database schema
- **Scope**: Directory structure, pyproject.toml, SQLite schema, base models
- **Files**: `pyproject.toml`, `src/mirage/db/schema.py`, `src/mirage/db/session.py`, `src/mirage/models/types.py`
- **Demo impact**: None visible (foundation)
- **Tests**: Schema creation, unique constraint enforcement
- **Docs**: `docs/pr-notes/PR01-scaffolding.md`
- **Interfaces touched**: Yes (base models)

### PR02: Core identity utilities (spec_hash, run_id)
- **Scope**: Deterministic ID generation functions
- **Files**: `src/mirage/core/identity.py`
- **Demo impact**: None visible (foundation)
- **Tests**: Determinism tests, hash collision resistance
- **Docs**: `docs/pr-notes/PR02-identity.md`
- **Interfaces touched**: No

### PR03: Normalization module (ffmpeg wrapper)
- **Scope**: Video normalization to canonical mp4
- **Files**: `src/mirage/normalize/ffmpeg.py`
- **Demo impact**: Can normalize videos via CLI
- **Tests**: Transcode correctness, duration matching
- **Docs**: `docs/pr-notes/PR03-normalization.md`
- **Interfaces touched**: No (uses frozen interface)

### PR04: Metrics engine - Tier 0 (ffmpeg/opencv/numpy)
- **Scope**: decode_ok, durations, fps, freeze, flicker, blur, scene cuts
- **Files**: `src/mirage/metrics/tier0.py`, `src/mirage/metrics/bundle.py`
- **Demo impact**: Can compute tier 0 metrics via CLI
- **Tests**: Metric value ranges, determinism
- **Docs**: `docs/pr-notes/PR04-metrics-tier0.md`
- **Interfaces touched**: No

### PR05: Metrics engine - Tier 1 (mediapipe)
- **Scope**: face detection, landmarks, mouth openness, blinks
- **Files**: `src/mirage/metrics/tier1.py`
- **Demo impact**: Can compute tier 1 metrics via CLI
- **Tests**: Face detection on test video, correlation bounds
- **Docs**: `docs/pr-notes/PR05-metrics-tier1.md`
- **Interfaces touched**: No

### PR06: Status badge derivation + full MetricBundleV1
- **Scope**: pass/flag/reject logic, combine tiers into bundle
- **Files**: `src/mirage/metrics/status.py`, update `bundle.py`
- **Demo impact**: CLI shows status badges
- **Tests**: Threshold-based badge assignment
- **Docs**: `docs/pr-notes/PR06-status-badges.md`
- **Interfaces touched**: No

### PR07: Mock provider adapter
- **Scope**: Stub provider that returns cached/synthetic video
- **Files**: `src/mirage/providers/mock.py`, `src/mirage/providers/base.py`
- **Demo impact**: Can "generate" variants (cached)
- **Tests**: Idempotency, artifact creation
- **Docs**: `docs/pr-notes/PR07-mock-provider.md`
- **Interfaces touched**: No

### PR08: Worker orchestrator (generation + normalization + metrics)
- **Scope**: Main worker loop connecting all components
- **Files**: `src/mirage/worker/orchestrator.py`, `src/mirage/worker/cli.py`
- **Demo impact**: `python -m mirage.worker run --experiment_id=demo` works
- **Tests**: End-to-end run pipeline, crash safety
- **Docs**: `docs/pr-notes/PR08-worker.md`
- **Interfaces touched**: No

### PR09: FastAPI app + experiment overview endpoint
- **Scope**: API server, GET /api/experiments/{id}
- **Files**: `src/mirage/api/app.py`, `src/mirage/api/routes/experiments.py`
- **Demo impact**: Can fetch experiment data via API
- **Tests**: API response shape, 404 handling
- **Docs**: `docs/pr-notes/PR09-api-experiments.md`
- **Interfaces touched**: No

### PR10: Run detail endpoint + artifact serving
- **Scope**: GET /api/runs/{id}, static file serving
- **Files**: `src/mirage/api/routes/runs.py`
- **Demo impact**: Can view run details, play videos
- **Tests**: Artifact path validation
- **Docs**: `docs/pr-notes/PR10-api-runs.md`
- **Interfaces touched**: No

### PR11: Human eval - task generation
- **Scope**: Pairwise task creation, randomization
- **Files**: `src/mirage/eval/tasks.py`, `src/mirage/api/routes/tasks.py`
- **Demo impact**: POST /api/experiments/{id}/tasks creates pairwise tasks
- **Tests**: Bias prevention (flip recorded), task count
- **Docs**: `docs/pr-notes/PR11-tasks.md`
- **Interfaces touched**: No

### PR12: Human eval - rating submission + aggregation
- **Scope**: POST /api/ratings, win rate calculation
- **Files**: `src/mirage/eval/ratings.py`, `src/mirage/aggregation/summary.py`
- **Demo impact**: Can submit ratings, see win rates
- **Tests**: Append-only ratings, aggregation correctness
- **Docs**: `docs/pr-notes/PR12-ratings.md`
- **Interfaces touched**: No

### PR13: Demo seeding script + smoke test
- **Scope**: Create demo experiment with cached artifacts
- **Files**: `scripts/seed_demo.py`, `scripts/smoke_demo.py`, `demo_assets/`
- **Demo impact**: One-command setup works
- **Tests**: Smoke test validates MetricBundleV1 keys
- **Docs**: `docs/pr-notes/PR13-demo-scripts.md`
- **Interfaces touched**: No

### PR14: Minimal web UI - experiment overview
- **Scope**: React/Next.js page showing variants + metrics
- **Files**: `ui/pages/experiment/[id].tsx`, `ui/components/`
- **Demo impact**: Browser shows experiment overview
- **Tests**: Component rendering
- **Docs**: `docs/pr-notes/PR14-ui-overview.md`
- **Interfaces touched**: No

### PR15: Minimal web UI - pairwise eval overlay
- **Scope**: Side-by-side video comparison, rating submission
- **Files**: `ui/components/EvalOverlay.tsx`
- **Demo impact**: Can complete pairwise comparisons in browser
- **Tests**: UI interaction tests
- **Docs**: `docs/pr-notes/PR15-ui-eval.md`
- **Interfaces touched**: No

### PR16: Export + recommended pick display
- **Scope**: Download button, win rate display
- **Files**: `ui/components/Results.tsx`, `src/mirage/api/routes/export.py`
- **Demo impact**: Full demo flow works end-to-end
- **Tests**: Export file integrity
- **Docs**: `docs/pr-notes/PR16-export.md`
- **Interfaces touched**: No

### PR17 (stretch): SyncNet integration (Tier 2)
- **Scope**: Optional LSE-D/LSE-C computation
- **Files**: `src/mirage/metrics/tier2_syncnet.py`
- **Demo impact**: SyncNet metrics shown if available
- **Tests**: Graceful degradation when unavailable
- **Docs**: `docs/pr-notes/PR17-syncnet.md`
- **Interfaces touched**: No

---

## Summary Table

| PR | Title | LOC Est | Priority |
|----|-------|---------|----------|
| 00 | Documentation setup | ~50 | Critical |
| 01 | Scaffolding + DB schema | ~250 | Critical |
| 02 | Identity utilities | ~100 | Critical |
| 03 | Normalization | ~150 | Critical |
| 04 | Metrics Tier 0 | ~250 | Critical |
| 05 | Metrics Tier 1 | ~250 | Critical |
| 06 | Status badges | ~100 | Critical |
| 07 | Mock provider | ~150 | Critical |
| 08 | Worker orchestrator | ~250 | Critical |
| 09 | API + experiments endpoint | ~200 | Critical |
| 10 | Runs endpoint + artifacts | ~150 | Critical |
| 11 | Task generation | ~200 | Critical |
| 12 | Ratings + aggregation | ~200 | Critical |
| 13 | Demo scripts | ~150 | Critical |
| 14 | UI overview | ~250 | Critical |
| 15 | UI eval overlay | ~200 | Critical |
| 16 | Export + results | ~150 | Critical |
| 17 | SyncNet (stretch) | ~200 | Stretch |

---

## TDD Policy

All PRs follow Test-Driven Development:

1. **Write tests first** - Define invariants as test cases before implementation
2. **Tests must fail initially** - Verify tests catch missing functionality
3. **Implement minimum code** - Write only enough code to pass tests
4. **Refactor** - Clean up while keeping tests green

## Pre-PR Cleanup Gate

Before each PR submission:
1. Simplify: remove dead code, reduce duplication, tighten naming
2. Boundary review: verify modules obey ARCHITECTURE.md boundaries
3. Interface review: check no new duplicate payload shapes
4. Invariant review: ensure idempotency + immutability rules hold
5. Run formatting/lint/tests locally, include commands in PR notes
