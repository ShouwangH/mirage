# PR17: SyncNet Integration (Tier 2 Metrics)

## Summary

Adds optional SyncNet-based lip sync quality metrics (LSE-D and LSE-C) as Tier 2 metrics
in MetricBundleV1. These metrics provide automated assessment of audio-visual synchronization
quality, which is critical for evaluating talking head generation models.

## What Changed

### New Files
- `src/mirage/adapter/syncnet/__init__.py` - Package init
- `src/mirage/adapter/syncnet/syncnet_model.py` - PyTorch model architecture
- `src/mirage/adapter/syncnet/syncnet_adapter.py` - Adapter with auto-download and inference
- `tests/test_syncnet.py` - Tests for SyncNet integration

### Modified Files
- `src/mirage/metrics/bundle.py` - Integrates SyncNet metrics computation

## Technical Details

### SyncNet Architecture

SyncNet is a dual-stream neural network that produces embeddings for both audio (MFCC features)
and video (lip region frames). By computing distances between these embeddings, we can measure
how well lip movements are synchronized with audio.

```
Audio Stream: MFCC (13 coeffs) → 1D CNN → 1024-dim embedding
Video Stream: Lip frames (112x112) → 3D CNN → 1024-dim embedding
```

### Metrics Computed

1. **LSE-D (Lip Sync Error - Distance)**: Average minimum distance between audio and video
   embeddings across temporal shifts. **Lower is better** (typical range: 5-10 for good sync).

2. **LSE-C (Lip Sync Error - Confidence)**: Difference between median and minimum distance,
   measuring how distinctly the best sync point stands out. **Higher is better** (typical: 3-8).

### Model Download

The SyncNet model weights (~23MB) are automatically downloaded on first use from:
```
https://www.robots.ox.ac.uk/~vgg/software/lipsync/data/syncnet_v2.model
```

Downloaded to: `models/syncnet_v2.pth`

### Graceful Degradation

The implementation gracefully handles missing dependencies:

1. **No PyTorch**: Returns `(None, None)` for LSE-D/LSE-C
2. **No librosa**: MFCC extraction fails gracefully
3. **Model download fails**: Returns `None` without crashing
4. **Insufficient video frames**: Returns `None`

### Dependencies

Optional dependencies for SyncNet:
- `torch` - PyTorch for neural network inference
- `librosa` - For MFCC audio feature extraction

If not installed, SyncNet metrics will be null (existing behavior).

## Usage Example

```python
from mirage.adapter.syncnet import compute_lse_metrics
from pathlib import Path

frames = [...]  # List of BGR numpy arrays
audio_path = Path("audio.wav")

lse_d, lse_c = compute_lse_metrics(frames, audio_path, fps=25.0)

if lse_d is not None:
    print(f"LSE-D: {lse_d:.2f} (lower = better sync)")
    print(f"LSE-C: {lse_c:.2f} (higher = more confident)")
```

## Testing

```bash
# Run SyncNet tests
pytest tests/test_syncnet.py -v

# Run all tests
pytest tests/ -q
```

Tests verify:
- Graceful import without PyTorch
- Returns None when dependencies unavailable
- MetricBundleV1 accepts both values and null for lse_d/lse_c
- Model architecture (skipped if PyTorch unavailable)

## Benchmark Reference

From Wav2Lip paper on LRS2 dataset:
- Real video LSE-D: ~6.736
- Wav2Lip LSE-D: ~6.386

Lower LSE-D indicates better lip synchronization.

## References

- [SyncNet Paper](https://www.robots.ox.ac.uk/~vgg/publications/2016/Chung16a/) - Original architecture
- [syncnet_python](https://github.com/joonson/syncnet_python) - Reference implementation
- [Wav2Lip](https://github.com/Rudrabha/Wav2Lip) - Evaluation methodology

## Boundary Compliance

- **Adapter layer**: SyncNet adapter follows same pattern as MediaPipe face adapter
- **Pure metrics**: Metric computation separated from I/O
- **Graceful degradation**: No hard failures when dependencies missing
- **Optional Tier 2**: Existing Tier 0/1 metrics unaffected
