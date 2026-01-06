# PR05: Metrics Engine - Tier 1 (mediapipe)

## Task + Plan

Implement Tier 1 metrics per METRICS.md using mediapipe:
- face_present_ratio, face_bbox_jitter, landmark_jitter
- mouth_open_energy, mouth_audio_corr
- blink_count, blink_rate_hz

## Scope

- Create `src/mirage/metrics/tier1.py` with mediapipe-based metrics
- TDD: Tests written first, implementation follows
- Graceful degradation when mediapipe not available
- Fix CI workflow hashFiles issue (move to step-level condition)

## Files Changed

- `src/mirage/metrics/tier1.py` (new) - Tier 1 metric functions
- `tests/test_metrics_tier1.py` (new) - 23 tests
- `.github/workflows/ci.yml` (modified) - Fix hashFiles issue

## Interfaces Touched

No - Produces dict compatible with MetricBundleV1 fields.

## Tests

23 tests added:
- **TestExtractFaceData**: Mediapipe face mesh extraction
- **TestComputeFacePresentRatio**: Face detection ratio
- **TestComputeFaceBboxJitter**: Bounding box stability
- **TestComputeLandmarkJitter**: Landmark stability
- **TestComputeMouthOpenEnergy**: Mouth movement variance
- **TestComputeMouthAudioCorr**: Mouth-audio correlation
- **TestComputeBlinkMetrics**: Blink detection via EAR
- **TestComputeTier1Metrics**: Integration tests
- **TestIntegrationWithVideo**: End-to-end with video

## Pre-PR Cleanup Checklist

1. [x] Simplify: Removed unused variables (in_blink)
2. [x] Boundary review:
   - `metrics/` contains only pure computations
   - No DB writes, no provider calls
3. [x] Interface review: Returns dict with MetricBundleV1 field names
4. [x] Invariant review: Metrics computed on decoded frames only
5. [x] Local commands:
   ```bash
   source .venv/bin/activate
   pip install mediapipe numpy opencv-python
   pytest tests/ -v  # 77 passed, 14 skipped
   ruff check .      # All checks passed
   ruff format --check .  # 20 files formatted
   ```

## Risks

- mediapipe not available on Python 3.14: Tests skip gracefully
- No face detected: Returns 0 for all metrics

## Demo Check

N/A - This PR is foundation only. No visible demo impact.

## Decisions

1. **Graceful degradation**: Returns None/0 when mediapipe unavailable
2. **Eye Aspect Ratio (EAR)**: Standard blink detection method
3. **Landmark indices**: Using mediapipe face mesh standard indices
4. **Inter-ocular normalization**: Landmark jitter normalized by eye distance
