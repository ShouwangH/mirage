# PR13: Adapter Refactoring

## Summary

Restructures external tool dependencies into a proper adapter layer with clear taxonomy:
- **adapter/media/**: IO/system boundary (ffprobe, video decoding)
- **adapter/vision/**: ML inference engines (mediapipe face detection)
- **metrics/**: Pure computations on domain types (stays in place)

## Taxonomy

| Category | Location | Examples |
|----------|----------|----------|
| IO/System boundary | adapter/ | ffprobe subprocess, cv2.VideoCapture, mediapipe inference |
| Feature extraction | metrics/ | grayscale, histogram, laplacian (deterministic transforms) |
| Business logic | metrics/ | jitter scores, blink detection, thresholds |

## Directory Structure

```
adapter/
  __init__.py              # Re-exports for convenience
  media/
    __init__.py
    probe.py               # ffprobe: VideoInfo, AudioInfo
    video_decode.py        # VideoReader, Frame, decode_frames
  vision/
    __init__.py
    mediapipe_face.py      # FaceExtractor, FaceTrack, FaceData
```

## Key Classes

### VideoReader (adapter/media/video_decode.py)
```python
with VideoReader(path) as reader:
    for frame in reader.iter_frames(max_frames=100, sample_every=2):
        process(frame.bgr)
```
- Context manager for resource cleanup
- Explicit parameters: max_frames, sample_every, resize_width
- Returns Frame objects with index, timestamp_ms, bgr

### FaceExtractor (adapter/vision/mediapipe_face.py)
```python
extractor = FaceExtractor()
track = extractor.extract_from_frames(frames, fps=30.0)
# track.face_data[i].detected, .bbox, .landmarks
```
- Stateful to avoid reinit overhead
- Returns FaceTrack with FaceData per frame
- Graceful fallback when mediapipe unavailable

## Changes

### New Files
- `src/mirage/adapter/media/__init__.py`
- `src/mirage/adapter/media/probe.py` (moved from media.py)
- `src/mirage/adapter/media/video_decode.py`
- `src/mirage/adapter/vision/__init__.py`
- `src/mirage/adapter/vision/mediapipe_face.py`

### Refactored
- `src/mirage/metrics/video_quality.py` - Uses VideoReader for frame decoding
- `src/mirage/metrics/face_metrics.py` - Uses FaceExtractor for detection
- `src/mirage/normalize/video.py` - Updated imports
- `tests/test_normalize.py` - Updated imports

### Removed
- `src/mirage/adapter/media.py` (moved to media/probe.py)

## Rationale

1. **Clear boundaries**: Adapters handle IO/external engines, metrics stay pure
2. **Explicit over implicit**: No hidden heuristics in performance params
3. **Testability**: Business logic can mock adapters
4. **Avoids drift**: Narrow adapter scopes prevent "adapter becomes core"

## Why This Split Is Correct

- **Adapters are thin**: "given file, get frames" / "given frames, get landmarks"
- **Metrics stay readable**: Deterministic computations on domain types
- **cv2 image ops stay in metrics**: grayscale, histogram, laplacian are transforms, not IO
