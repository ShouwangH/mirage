"""MetricBundleV1 assembly from tier0 + tier1 + status.

This module provides the main compute_metrics entry point that:
1. Computes Tier 0 metrics (ffmpeg/opencv/numpy)
2. Computes Tier 1 metrics (mediapipe)
3. Derives status badge from metrics
4. Returns a complete MetricBundleV1

Per METRICS.md, Tier 2 (SyncNet) is optional and set to null until PR17.
"""

from __future__ import annotations

from pathlib import Path

from mirage.metrics.status import compute_status_badge
from mirage.metrics.tier0 import compute_tier0_metrics, decode_video
from mirage.metrics.tier1 import compute_tier1_metrics
from mirage.models.types import MetricBundleV1


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


def compute_metrics(video_path: Path, audio_path: Path) -> MetricBundleV1:
    """Compute complete MetricBundleV1 from canonical video and audio.

    This is the main entry point per IMPLEMENTATION_PLAN.md interface spec:
        def compute_metrics(canon_path: Path, audio_path: Path) -> MetricBundleV1

    Args:
        video_path: Path to canonical video file.
        audio_path: Path to canonical audio file.

    Returns:
        Complete MetricBundleV1 with all metrics and status.
    """
    # Compute Tier 0 metrics
    tier0 = compute_tier0_metrics(video_path, audio_path)

    # Decode video for Tier 1 (if decode successful)
    if tier0["decode_ok"]:
        frames = decode_video(video_path)
        fps = tier0["fps"]

        # Extract audio envelope for mouth-audio correlation
        audio_envelope = _extract_audio_envelope(audio_path, len(frames), fps)

        # Compute Tier 1 metrics
        tier1 = compute_tier1_metrics(frames, audio_envelope, fps)
    else:
        # Failed decode - use default Tier 1 values
        tier1 = {
            "face_present_ratio": 0.0,
            "face_bbox_jitter": 0.0,
            "landmark_jitter": 0.0,
            "mouth_open_energy": 0.0,
            "mouth_audio_corr": 0.0,
            "blink_count": None,
            "blink_rate_hz": None,
        }

    # Compute status badge
    status_result = compute_status_badge(
        decode_ok=tier0["decode_ok"],
        face_present_ratio=tier1["face_present_ratio"],
        av_duration_delta_ms=tier0["av_duration_delta_ms"],
        flicker_score=tier0["flicker_score"],
        freeze_frame_ratio=tier0["freeze_frame_ratio"],
        blur_score=tier0["blur_score"],
        mouth_audio_corr=tier1["mouth_audio_corr"],
    )

    # Assemble MetricBundleV1
    return MetricBundleV1(
        # Tier 0
        decode_ok=tier0["decode_ok"],
        video_duration_ms=tier0["video_duration_ms"],
        audio_duration_ms=tier0["audio_duration_ms"],
        av_duration_delta_ms=tier0["av_duration_delta_ms"],
        fps=tier0["fps"],
        frame_count=tier0["frame_count"],
        scene_cut_count=tier0["scene_cut_count"],
        freeze_frame_ratio=tier0["freeze_frame_ratio"],
        flicker_score=tier0["flicker_score"],
        blur_score=tier0["blur_score"],
        frame_diff_spike_count=tier0["frame_diff_spike_count"],
        # Tier 1
        face_present_ratio=tier1["face_present_ratio"],
        face_bbox_jitter=tier1["face_bbox_jitter"],
        landmark_jitter=tier1["landmark_jitter"],
        mouth_open_energy=tier1["mouth_open_energy"],
        mouth_audio_corr=tier1["mouth_audio_corr"],
        blink_count=tier1["blink_count"],
        blink_rate_hz=tier1["blink_rate_hz"],
        # Tier 2 (optional, null until SyncNet PR17)
        lse_d=None,
        lse_c=None,
        # Status
        status_badge=status_result["badge"],
        reasons=status_result["reasons"],
    )
