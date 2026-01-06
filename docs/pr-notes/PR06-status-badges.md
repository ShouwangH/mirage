# PR06: Status Badge Derivation

## Summary

Implements status badge derivation (pass/flagged/reject) from computed metrics and creates the `compute_metrics` entry point that combines Tier 0 + Tier 1 metrics into a complete `MetricBundleV1`.

## Files Changed

- `src/mirage/metrics/status.py` - Status badge derivation logic
- `src/mirage/metrics/bundle.py` - MetricBundleV1 assembly
- `tests/test_status.py` - 17 tests for badge derivation
- `tests/test_bundle.py` - 11 tests for bundle assembly

## Implementation Details

### Status Badge Logic (from METRICS.md)

**Reject (hard failure):**
- `decode_ok = false`
- `face_present_ratio < 0.2`
- `av_duration_delta_ms > 500ms`

**Flagged (review):**
- `flicker_score > 10.0`
- `freeze_frame_ratio > 0.3`
- `blur_score < 20.0`
- `mouth_audio_corr < -0.1`

**Pass:**
- Not reject and not flagged

### Threshold Constants

```python
# Reject thresholds
REJECT_FACE_PRESENT_FLOOR = 0.2
REJECT_AV_DELTA_CEILING = 500  # ms

# Flag thresholds
FLAG_FLICKER_CEILING = 10.0
FLAG_FREEZE_CEILING = 0.3
FLAG_BLUR_FLOOR = 20.0
FLAG_MOUTH_AUDIO_CORR_FLOOR = -0.1
```

### compute_metrics Entry Point

The `compute_metrics(video_path, audio_path) -> MetricBundleV1` function:

1. Computes Tier 0 metrics via `compute_tier0_metrics`
2. If decode succeeds, decodes video and computes Tier 1 metrics
3. Extracts audio envelope for mouth-audio correlation
4. Derives status badge from metrics
5. Returns complete `MetricBundleV1` with all fields

### Audio Envelope Extraction

For mouth-audio correlation, audio is extracted to raw PCM using ffmpeg:
- Sample rate: 16kHz mono
- Format: 32-bit float
- RMS computed per video frame window

## Testing

```bash
pytest tests/test_status.py tests/test_bundle.py -v
```

- 17 status badge tests (thresholds, priorities, boundary conditions)
- 11 bundle assembly tests (field validation, failure handling, ranges)

## Design Decisions

1. **Threshold Values**: Demo-tuned per METRICS.md. UI should label these as "review signals" not hard requirements.

2. **Priority**: Reject conditions override flagged. Both types of reasons are collected in the output.

3. **Graceful Degradation**: Failed video decode returns reject badge with default Tier 1 values (zeros/nulls).

4. **Tier 2 (SyncNet)**: Set to null (`lse_d=None`, `lse_c=None`) until PR17.

## Boundary Compliance

- `src/mirage/metrics/` is pure computation (boundary D)
- No DB writes, provider calls, or UI concerns
- Depends only on opencv/mediapipe/ffmpeg

## Verification

```bash
ruff check .
ruff format --check .
pytest tests/ -v
```
