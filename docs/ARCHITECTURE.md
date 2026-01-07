# ARCHITECTURE.md — a-roll eval loop (mvp)

## 0) architecture philosophy (what we’re optimizing for)

- correctness at boundaries: idempotency, immutability, reproducibility
- minimal moving parts: single machine, sqlite, filesystem artifacts
- explicit lineage: every clip ties back to a fixed spec + fixed inputs
- graceful degradation: syncnet is optional; provider generation can be cached

this is not a platform. it’s a tight loop demo that still behaves like production software.

---

## 1) components

### 1.1 web app (ui + api)
choose one:
- **option a (simpler for demo):** next.js (ui) + next.js api routes (backend) + a local worker process
- **option b (cleaner separation):** next.js (ui) + fastapi (api) + local worker process

both are fine. mvp bias: option a.

### 1.2 worker
a single local process that:
- generates variants (provider call)
- normalizes artifacts (ffmpeg transcode)
- computes metrics
- writes results to sqlite

worker can be invoked as:
- `python -m worker run --experiment_id=...`
or
- `node scripts/run_worker.mjs ...`
but keep it one language if possible.

#### worker architecture
the worker uses a two-layer design:

**WorkerOrchestrator** (thin coordination layer):
- claims queued runs atomically via `SELECT ... FOR UPDATE SKIP LOCKED`
- builds RunContext from database lookups
- delegates to RunProcessor
- handles status updates and error recording

**RunProcessor** (pure single-run processing):
- receives pre-built RunContext with all paths, IDs, and inputs
- executes pipeline: provider → normalize → metrics
- no status management; just returns results or raises

**RunContext** (immutable context):
- run_id, experiment_id, item_id, variant_key, spec_hash
- gen_input (GenerationInput with all provider params)
- run_output_dir (Path for artifacts)

this separation allows RunProcessor to be tested in isolation and keeps
orchestration concerns (claiming, retries, status) separate from processing logic.

---

## 2) storage model

### 2.1 sqlite is the source of truth
stores:
- experiments, runs, provider calls, metric results, human tasks/ratings

### 2.2 filesystem (or s3 later) stores blobs
all artifacts are immutable and stored under a deterministic directory layout.

**artifact root:**
`artifacts/`

**run layout:**
`artifacts/runs/{run_id}/`
- `raw/raw.mp4` — raw video from provider (stable name, not provider_job_id)
- `output_canon.mp4` — normalized canonical video (required; browser-safe)
- `input_audio.wav` (optional cached copy)
- `preview.gif` (optional)
- `metrics.json` (optional mirror of db)
- `debug/` (optional overlays)

note: raw artifacts are named by run_id directory, not provider_job_id. the job_id is
provider-specific metadata stored in provider_calls table, not a stable file identifier.

---

## 3) identity + idempotency strategy (non-negotiable)

### 3.1 spec_hash
`spec_hash = sha256( canonical_json({
  provider, model, model_version,
  rendered_prompt,
  params_json,
  seed,
  input_audio_sha256,
  ref_image_sha256 (or null),
}))`

### 3.2 run_id
`run_id = sha256(experiment_id + item_id + variant_key + spec_hash)`

### 3.3 provider idempotency key
`provider_idempotency_key = sha256(provider + spec_hash)`

### 3.4 invariants enforced by db constraints
- `runs` unique: `(experiment_id, item_id, variant_key)`
- `provider_calls` unique: `(provider, provider_idempotency_key)`
- `metric_results` unique: `(run_id, metric_name, metric_version)`
- `human_ratings` unique: `(task_id, rater_id, submitted_at)` (or allow multiple with versioning; but don't overwrite)

**meaning:** retries are safe. re-runs do not double spend. artifacts are never overwritten.

### 3.5 centralized identity utilities (`core/identity.py`)
all identity/hash computations are centralized:

- `compute_spec_hash(...)` — deterministic spec hash from inputs
- `compute_run_id(...)` — deterministic run_id from experiment/item/variant/spec
- `compute_provider_idempotency_key(...)` — deduplication key for provider calls
- `sha256_file(path)` — streaming file hash (64KB chunks, memory-efficient)
- `seed_from_variant_key(variant_key)` — deterministic seed extraction

**important:** always use `sha256_file()` instead of `hashlib.sha256(file.read_bytes())`.
streaming avoids loading large video files into memory.

---

## 4) state machines

### 4.1 Run status
- `queued` → `running` → `succeeded`
- `queued` → `running` → `failed`

terminal states: `succeeded`, `failed` (never transition out)

### 4.2 ProviderCall status
- `created` → `completed`
- `created` → `failed`

on completion, provider_call stores:
- `raw_artifact_uri` — path to raw video for cache reuse
- `raw_artifact_sha256` — hash for verification

failed calls may retry with incremented `attempt`.

---

## 5) generation boundary (provider call correctness)

### 5.1 activity contract
generation is the only expensive side effect. it must be idempotent.

pseudo-logic:

1) load `run`
2) if `run.status == succeeded`: return (no-op)
3) compute `provider_idempotency_key`
4) query existing provider_call by (provider, idempotency_key)
   - if exists and completed: use `raw_artifact_uri` from DB (not guessed path)
   - otherwise: create new provider_call with status=created
5) call provider with idempotency header if supported
6) write provider output to `{run_id}/raw/raw.mp4`
7) update provider_call with:
   - status=completed
   - raw_artifact_uri (actual path)
   - raw_artifact_sha256 (for verification)
   - cost/latency metadata
8) transcode to canonical `output_canon.mp4`
9) compute sha256 of canonical output
10) mark run succeeded with `output_canon_uri` + sha256

**crash safety:**
- if crash before finalize: tmp files remain; safe to delete on next run
- if crash before db commit: run isn’t succeeded; retry will re-check and re-run safely
- if crash after db commit: retries become no-ops

---

## 6) normalization boundary (ffmpeg)

every output must be normalized before:
- metrics
- browser playback
- side-by-side eval

canonical format:
- mp4 (h264) + aac audio
- fixed fps target (e.g. 30)
- consistent duration trimming/padding policy:
  - trim video to audio duration (or vice versa) deterministically
  - record `av_duration_delta_ms`

---

## 7) metric suite implementation (compute_metrics contract)

### 7.1 function signature
`compute_metrics(run_id) -> MetricBundleV1`

### 7.2 MetricBundleV1 fields (suggested)
tier 0:
- `decode_ok: bool`
- `video_duration_ms: int`
- `audio_duration_ms: int`
- `av_duration_delta_ms: int`
- `fps: float`
- `frame_count: int`
- `scene_cut_count: int`
- `freeze_frame_ratio: float` (0..1)
- `flicker_score: float` (higher = more flicker)
- `blur_score: float` (lower = blurrier; document exact definition)
- `frame_diff_spike_count: int`

tier 1 (mediapipe):
- `face_present_ratio: float` (0..1)
- `face_bbox_jitter: float`
- `landmark_jitter: float`
- `mouth_open_energy: float`
- `mouth_audio_corr: float` (-1..1)
- `blink_count: int` (optional)
- `blink_rate_hz: float` (optional)

tier 2 (syncnet, optional):
- `lse_d: float` (optional)
- `lse_c: float` (optional)

### 7.3 metric versions
every metric result must store:
- `metric_name`
- `metric_version` (e.g., `v1`)
so changes don’t silently invalidate comparisons.

---

## 8) human eval correctness

### 8.1 pairwise task generation
for N variants, generate a small set:
- for 3 variants: AB, BC, AC
- for 5 variants: either full pairwise (10) or a tournament-style subset (mvp: subset)

### 8.2 left/right bias prevention
- randomize presentation order
- store `presented_left_run_id`, `presented_right_run_id` (or store `flip: bool`)

### 8.3 aggregation
- `win_rate` = wins / (wins + losses), ignoring ties/skips
- store per-question win rates:
  - realism
  - lip-sync
  - target match (optional)

---

## 9) api surface (minimal)

- `GET /api/experiments/:id` → overview payload (runs + metrics + ratings summary)
- `POST /api/experiments/:id/evaluate_tasks` → create tasks (if not exists)
- `POST /api/ratings` → submit a rating (task_id, choices, flip info)
- `GET /api/runs/:id` → run details (spec + artifact paths + raw metrics)

generation/metrics execution can be:
- manual: run worker via cli
- or endpoint-triggered for demo: `POST /api/experiments/:id/run` (dangerous; ok in local demo)

---

## 10) explicit non-goals enforced by design

- no prompt mutation: variants are created by explicit user action; no auto-rewrites
- no hidden “agent loop”: suggestions are advisory; any change creates a new variant with a diff
- no multi-tenant concerns: local-only, demo-only

---

## 11) what makes this “correct” (quick checklist)

- [ ] deterministic run_id + spec_hash includes input hashes
- [ ] unique constraints prevent duplicate runs and duplicate provider spend
- [ ] artifacts are immutable; no overwrite
- [ ] canonical transcode before metrics/playback
- [ ] human eval randomizes left/right and records it
- [ ] syncnet optional; tool degrades gracefully without it
