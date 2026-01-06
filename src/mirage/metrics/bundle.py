"""MetricBundleV1 assembly from video_quality + face_metrics + status.

This module provides the main compute_metrics entry point that:
1. Uses adapters for IO (video decoding, face detection)
2. Calls pure metric functions with extracted data
3. Derives status badge from metrics
4. Returns a complete MetricBundleV1

Per METRICS.md, SyncNet metrics are optional and set to null until PR17.
"""

from __future__ import annotations

from pathlib import Path

from mirage.adapter.media.video_decode import VideoReader
from mirage.adapter.vision.mediapipe_face import FaceExtractor
from mirage.metrics.face_metrics import (
    _compute_eye_aspect_ratio,
    _compute_mouth_openness,
    compute_face_metrics,
)
from mirage.metrics.status import compute_status_badge
from mirage.metrics.video_quality import compute_video_quality_metrics
from mirage.models.types import MetricBundleV1

# Module-level face extractor for reuse (avoids reinit overhead)
_face_extractor: FaceExtractor | None = None


def _get_face_extractor() -> FaceExtractor:
    """Get or create the shared FaceExtractor instance."""
    global _face_extractor
    if _face_extractor is None:
        _face_extractor = FaceExtractor()
    return _face_extractor


def _extract_audio_envelope(audio_path: Path, num_frames: int, fps: float) -> list:
    """Extract audio RMS envelope per frame.

    Args:
        audio_path: Path to audio file.
        num_frames: Number of video frames.
        fps: Video frames per second.

    Returns:
        List of RMS values per frame window.
    """
    if num_frames == 0 or fps <= 0:
        return []

    try:
        import subprocess

        import numpy as np

        # Extract raw audio using ffmpeg
        result = subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(audio_path),
                "-f",
                "f32le",
                "-acodec",
                "pcm_f32le",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-",
            ],
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            return [0.0] * num_frames

        audio_data = np.frombuffer(result.stdout, dtype=np.float32)
        if len(audio_data) == 0:
            return [0.0] * num_frames

        # Compute RMS per frame window
        samples_per_frame = int(16000 / fps)
        envelope = []

        for i in range(num_frames):
            start = i * samples_per_frame
            end = start + samples_per_frame

            if start >= len(audio_data):
                envelope.append(0.0)
            else:
                chunk = audio_data[start:end]
                rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) > 0 else 0.0
                envelope.append(rms)

        return envelope

    except (ImportError, subprocess.TimeoutExpired, Exception):
        return [0.0] * num_frames


def _extract_face_data(frames: list, fps: float) -> list:
    """Extract face data from frames using adapter.

    Converts adapter output to dict format expected by metrics.

    Args:
        frames: List of Frame objects from VideoReader.
        fps: Video frame rate.

    Returns:
        List of face data dicts (or None if no face detected).
    """
    extractor = _get_face_extractor()
    track = extractor.extract_from_frames(frames, fps=fps)

    # Convert FaceTrack to dict format with derived values
    results = []
    for fd in track.face_data:
        if fd.detected and len(fd.landmarks) > 0:
            mouth_openness = _compute_mouth_openness(fd.landmarks)
            ear = _compute_eye_aspect_ratio(fd.landmarks)

            results.append(
                {
                    "bbox": fd.bbox,
                    "landmarks": fd.landmarks,
                    "mouth_openness": mouth_openness,
                    "eye_aspect_ratio": ear,
                }
            )
        else:
            results.append(None)

    return results


def compute_metrics(video_path: Path, audio_path: Path) -> MetricBundleV1:
    """Compute complete MetricBundleV1 from canonical video and audio.

    This is the main entry point per IMPLEMENTATION_PLAN.md interface spec:
        def compute_metrics(canon_path: Path, audio_path: Path) -> MetricBundleV1

    Uses adapters for IO operations, passes domain data to pure metric functions.

    Args:
        video_path: Path to canonical video file.
        audio_path: Path to canonical audio file.

    Returns:
        Complete MetricBundleV1 with all metrics and status.
    """
    # Compute video quality metrics
    video_quality = compute_video_quality_metrics(video_path, audio_path)

    # Decode video and extract face data for face metrics (if decode successful)
    if video_quality["decode_ok"]:
        fps = video_quality["fps"]

        # Use adapter to decode frames
        try:
            with VideoReader(video_path) as reader:
                frames = list(reader.iter_frames())
                frame_size = (reader.width, reader.height)
        except (FileNotFoundError, RuntimeError):
            frames = []
            frame_size = (320, 240)

        if len(frames) > 0:
            # Extract audio envelope for mouth-audio correlation
            audio_envelope = _extract_audio_envelope(audio_path, len(frames), fps)

            # Use adapter to extract face data
            face_data = _extract_face_data(frames, fps)

            # Compute face metrics (pure computation)
            face = compute_face_metrics(face_data, frame_size, audio_envelope, fps)
        else:
            face = _default_face_metrics()
    else:
        # Failed decode - use default face metrics
        face = _default_face_metrics()

    # Compute status badge
    status_result = compute_status_badge(
        decode_ok=video_quality["decode_ok"],
        face_present_ratio=face["face_present_ratio"],
        av_duration_delta_ms=video_quality["av_duration_delta_ms"],
        flicker_score=video_quality["flicker_score"],
        freeze_frame_ratio=video_quality["freeze_frame_ratio"],
        blur_score=video_quality["blur_score"],
        mouth_audio_corr=face["mouth_audio_corr"],
    )

    # Assemble MetricBundleV1
    return MetricBundleV1(
        # Video quality metrics
        decode_ok=video_quality["decode_ok"],
        video_duration_ms=video_quality["video_duration_ms"],
        audio_duration_ms=video_quality["audio_duration_ms"],
        av_duration_delta_ms=video_quality["av_duration_delta_ms"],
        fps=video_quality["fps"],
        frame_count=video_quality["frame_count"],
        scene_cut_count=video_quality["scene_cut_count"],
        freeze_frame_ratio=video_quality["freeze_frame_ratio"],
        flicker_score=video_quality["flicker_score"],
        blur_score=video_quality["blur_score"],
        frame_diff_spike_count=video_quality["frame_diff_spike_count"],
        # Face metrics
        face_present_ratio=face["face_present_ratio"],
        face_bbox_jitter=face["face_bbox_jitter"],
        landmark_jitter=face["landmark_jitter"],
        mouth_open_energy=face["mouth_open_energy"],
        mouth_audio_corr=face["mouth_audio_corr"],
        blink_count=face["blink_count"],
        blink_rate_hz=face["blink_rate_hz"],
        # SyncNet metrics (optional, null until PR17)
        lse_d=None,
        lse_c=None,
        # Status
        status_badge=status_result["badge"],
        reasons=status_result["reasons"],
    )


def _default_face_metrics() -> dict:
    """Return default face metrics for failed decode."""
    return {
        "face_present_ratio": 0.0,
        "face_bbox_jitter": 0.0,
        "landmark_jitter": 0.0,
        "mouth_open_energy": 0.0,
        "mouth_audio_corr": 0.0,
        "blink_count": None,
        "blink_rate_hz": None,
    }
