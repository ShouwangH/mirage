# API.md — minimal contracts

## overview payload
`GET /api/experiments/{experiment_id}`

returns:
- experiment metadata
- dataset item metadata
- runs[] with:
  - run_id, variant_key, status
  - output_canon_uri (if succeeded)
  - metrics (latest MetricBundleV1)
  - status_badge + reasons[]
  - human_summary (win rates, recommended pick)

## run detail
`GET /api/runs/{run_id}`
returns:
- run + spec (resolved + rendered)
- artifact paths + sha256
- metric_results[]
- provider_calls[] (sanitized)

## create pairwise tasks
`POST /api/experiments/{experiment_id}/tasks`
creates pairwise tasks if missing.
returns tasks to rate.

## submit rating
`POST /api/ratings`
body:
- task_id
- rater_id
- choices: realism, lipsync, targetmatch (optional)
- flip (bool) or presented_left/right ids

returns:
- updated experiment summary (optional)

## run pipeline (demo only)
either:
- no API (run worker via CLI), or
- `POST /api/experiments/{experiment_id}/run` (local only)
  - triggers generation + metrics for queued runs

**warning:** do not ship “run pipeline” endpoint publicly. local demo only.
