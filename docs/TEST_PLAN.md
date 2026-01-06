# TEST_PLAN.md — what “correct” means

## goal
prevent the classic demo failures:
- duplicated provider calls (double spend)
- overwritten artifacts (non-reproducible)
- inconsistent run meaning (spec drift)
- biased human eval (left/right bias)
- unplayable outputs (codec hell)

## required tests (unit/integration)

### idempotency: run identity
- given same inputs + spec, spec_hash is stable
- given same experiment/item/variant, run_id is stable

### uniqueness constraints
- cannot insert duplicate run for (experiment,item,variant_key)
- cannot insert duplicate provider_call for (provider, idempotency_key)
- cannot insert duplicate metric_result for (run, name, version)

### crash safety (simulated)
- simulate crash after provider returns but before db commit:
  - rerun worker does not create a second provider_call
- simulate crash mid-upload:
  - tmp files remain, but final artifact not marked succeeded

### artifact immutability
- once run status == succeeded, rerun worker must not overwrite output_canon.mp4
- output_sha256 must match file content

### normalization correctness
- normalized output plays in browser (smoke test)
- video_duration and audio_duration measured correctly

### metrics smoke tests
- compute_metrics returns all required keys with correct types
- values are within broad bounds (not exact equality):
  - ratios in [0,1]
  - correlation in [-1,1]

### human eval bias checks
- left/right presentation randomized across tasks
- flip is stored and used in aggregation

## manual demo checklist
- [ ] open overview page, plays videos
- [ ] click evaluate overlay, submit votes
- [ ] win rates update
- [ ] recommended pick visible
- [ ] review queue shows at least one flagged/reject reason (if present)
- [ ] export works
