"""Adapter module for external tools and IO boundaries.

Adapters wrap external dependencies behind domain-focused interfaces.
Business logic should use adapters rather than calling external tools directly.

Structure:
- adapter/media/   - ffprobe, video decoding (file IO)
- adapter/vision/  - mediapipe face detection (ML inference)
"""

# Re-export commonly used items for convenience
from mirage.adapter.media import (
    AudioInfo,
    Frame,
    VideoInfo,
    VideoReader,
    check_available,
    probe_audio,
    probe_video,
)
from mirage.adapter.vision import FaceData, FaceExtractor, FaceTrack

__all__ = [
    # Media
    "AudioInfo",
    "Frame",
    "VideoInfo",
    "VideoReader",
    "check_available",
    "probe_audio",
    "probe_video",
    # Vision
    "FaceData",
    "FaceExtractor",
    "FaceTrack",
]
