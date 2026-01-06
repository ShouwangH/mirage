# PR04: Metrics Engine - Tier 0 (ffmpeg/opencv/numpy)

## Task + Plan

Implement Tier 0 metrics per METRICS.md:
- decode_ok, video/audio duration, fps, frame_count
- scene_cut_count, freeze_frame_ratio
- flicker_score, blur_score, frame_diff_spike_count

## Scope

- Create `src/mirage/metrics/tier0.py` with metric computation functions
- TDD: Tests written first, implementation follows
- Graceful degradation when opencv not available

## Files Changed

- `src/mirage/metrics/__init__.py` (new)
- `src/mirage/metrics/tier0.py` (new) - Tier 0 metric functions
- `tests/test_metrics_tier0.py` (new) - 21 tests

## Interfaces Touched

No - Produces dict compatible with MetricBundleV1 fields.

## Tests

21 tests added:
- **TestGetAvInfo**: Duration extraction, missing file handling
- **TestDecodeVideo**: Frame decoding with opencv
- **TestComputeFreezeFrameRatio**: Frozen frame detection
- **TestComputeFlickerScore**: Luminance stability
- **TestComputeBlurScore**: Laplacian variance
- **TestComputeSceneCuts**: Histogram-based scene detection
- **TestComputeFrameDiffSpikes**: Glitch detection
- **TestComputeTier0Metrics**: Integration tests

## Pre-PR Cleanup Checklist

1. [x] Simplify: Removed unused TYPE_CHECKING import
2. [x] Boundary review:
   - `metrics/` contains only pure computations
   - No DB writes, no provider calls
3. [x] Interface review: Returns dict with MetricBundleV1 field names
4. [x] Invariant review: Metrics computed on canonical video only
5. [x] Local commands:
   ```bash
   source .venv/bin/activate
   pip install numpy opencv-python
   pytest tests/ -v  # 57 passed, 11 skipped
   ruff check .      # All checks passed
   ruff format --check .  # 18 files formatted
   ```

## Risks

- opencv not installed: Tests skip gracefully, metrics return decode_ok=False
- ffmpeg not installed: Integration tests skipped

## Demo Check

N/A - This PR is foundation only. No visible demo impact.

## Decisions

1. **Graceful degradation**: Returns decode_ok=False when video can't be processed
2. **Threshold tuning**: Scene cut threshold set to 0.5 (chi-squared histogram diff)
3. **Blur score**: Higher = sharper (variance of Laplacian)
4. **Frame-based**: All metrics computed from decoded frames for consistency
