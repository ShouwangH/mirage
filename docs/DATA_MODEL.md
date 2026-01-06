# DATA_MODEL.md — schema + invariants

## mental model
this is an immutable run ledger:
- an Experiment creates Runs
- each Run has a deterministic identity (spec_hash + run_id)
- generation produces immutable artifacts
- metrics and human ratings attach to runs
- we never mutate the meaning of an existing run

## tables (minimum)

### dataset_items
- item_id (pk)
- subject_id
- source_video_uri
- audio_uri
- ref_image_uri (nullable)
- metadata_json

### generation_specs
- generation_spec_id (pk)
- provider
- model
- model_version (nullable)
- prompt_template
- params_json
- seed_policy_json

### experiments
- experiment_id (pk)
- generation_spec_id (fk)
- status (draft/running/complete)
- created_at

### runs
- run_id (pk)
- experiment_id (fk)
- item_id (fk)
- variant_key (e.g., seed=22)
- spec_hash (sha256 canonical json)
- status (queued/running/succeeded/failed)
- output_canon_uri (nullable)
- output_sha256 (nullable)
- started_at, ended_at
- error_code (nullable)
- error_detail (nullable)

**unique constraint**
- UNIQUE(experiment_id, item_id, variant_key)

### provider_calls
- provider_call_id (pk)
- run_id (fk)
- provider
- provider_idempotency_key
- attempt
- status (in_flight/succeeded/failed_transient/failed_permanent)
- provider_job_id (nullable)
- request_json_sanitized (nullable)
- response_json_sanitized (nullable)
- cost_usd (nullable)
- latency_ms (nullable)
- created_at

**unique constraint**
- UNIQUE(provider, provider_idempotency_key)

### metric_results
- metric_result_id (pk)
- run_id (fk)
- metric_name
- metric_version
- value_json
- status (succeeded/failed)
- error_detail (nullable)
- created_at

**unique constraint**
- UNIQUE(run_id, metric_name, metric_version)

### human_tasks
- task_id (pk)
- experiment_id (fk)
- task_type (pairwise)
- left_run_id
- right_run_id
- presented_left_run_id
- presented_right_run_id
- flip (bool)
- status (open/assigned/done/void)
- created_at

### human_ratings
- rating_id (pk)
- task_id (fk)
- rater_id
- choice_realism (left/right/tie/skip)
- choice_lipsync (left/right/tie/skip)
- choice_targetmatch (left/right/tie/skip) (optional)
- notes (nullable)
- created_at

## invariants (the “correctness proof” we enforce)
1) runs are unique per (experiment,item,variant_key)
2) provider spend is deduped by provider_idempotency_key
3) artifacts are immutable and content-addressed by sha256
4) run meaning is stable because spec_hash includes input artifact hashes
5) state transitions are monotonic: succeeded/failed are terminal
6) ratings never overwrite; edits create a new row (append-only)

## id construction (must match ARCHITECTURE.md)
- spec_hash includes: provider/model/version + rendered prompt + params + seed + input hashes
- run_id includes: experiment_id + item_id + variant_key + spec_hash
- provider_idempotency_key includes: provider + spec_hash
