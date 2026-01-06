"""Vision adapters for ML-based analysis.

Adapters for external vision engines with model inference:
- mediapipe_face: Face mesh detection and landmark extraction
"""

from mirage.adapter.vision.mediapipe_face import FaceData, FaceExtractor, FaceTrack

__all__ = [
    "FaceData",
    "FaceExtractor",
    "FaceTrack",
]
