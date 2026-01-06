# README.md — a-roll eval loop (mvp)

## what this is
a small internal-style tool that:
- generates 3–5 talking-head variants from the same canonical audio + target constraints
- computes a cheap metric suite (sanity + stability + face/mouth signals)
- optionally computes SyncNet lip-sync proxy (LSE-D/LSE-C)
- runs a short pairwise human preference step and recommends the best variant

this is an evaluation loop. it does not “solve realism.”

## quickstart (local demo)
### 1) prerequisites
- ffmpeg + ffprobe installed (see SETUP.md)
- python 3.10+ (or node 18+ depending on implementation)
- demo assets present in `demo_assets/` (or run the seed script)

### 2) install
- `pip install -r requirements.txt` (and optionally `requirements-syncnet.txt`)

### 3) seed demo
- `python scripts/seed_demo.py`
  - creates a demo experiment with 1–2 dataset items and 3–5 variants (seeds)

### 4) run pipeline
- `python scripts/run_experiment.py --experiment_id demo`

### 5) open UI
- `npm run dev` (or `python -m app`)
- open: `http://localhost:3000/experiment/demo`

## demo script (2 minutes)
1) open the experiment overview
2) show variants with metrics + pass/flag/reject
3) click “evaluate variants”
4) complete pairwise votes
5) show “recommended for export” + review queue reasons
6) export recommended clip

## project principles
- specs are immutable; changes create a new variant
- artifacts are immutable; never overwrite
- idempotency is enforced by deterministic ids and unique constraints
- metrics are labels and proxies, not truth

## docs
- PRD.md — product scope and frozen demo
- ARCHITECTURE.md — boundaries + invariants
- DATA_MODEL.md — tables + constraints
- METRICS.md — definitions + formulas
- API.md — payloads
- RUNBOOK.md — troubleshooting
- TEST_PLAN.md — what correctness means here
- docs/adrs/ — architectural decisions
- docs/pr-notes/ — per-PR learning notes
