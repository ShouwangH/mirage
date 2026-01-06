"""Media adapters for video/audio file operations.

Adapters for IO/system boundary operations:
- probe: ffprobe-based metadata extraction
- video_decode: frame iteration from video files
- audio_envelope: audio RMS extraction for lip-sync
"""

from mirage.adapter.media.audio_envelope import AudioDecodeError, extract_rms_envelope
from mirage.adapter.media.probe import (
    AudioInfo,
    VideoInfo,
    check_available,
    probe_audio,
    probe_video,
)
from mirage.adapter.media.video_decode import Frame, VideoReader

__all__ = [
    "AudioDecodeError",
    "AudioInfo",
    "Frame",
    "VideoInfo",
    "VideoReader",
    "check_available",
    "extract_rms_envelope",
    "probe_audio",
    "probe_video",
]
