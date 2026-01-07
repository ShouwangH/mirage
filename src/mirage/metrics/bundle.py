"""MetricBundleV1 assembly from video_quality + face_metrics + syncnet + status.

This module is the thin orchestrator that:
1. Calls adapters for IO (video decoding, face detection, audio extraction)
2. Passes domain objects to pure metric functions
3. Computes optional SyncNet metrics (Tier 2)
4. Derives status badge from metrics
5. Returns a complete MetricBundleV1
"""

from __future__ import annotations

import logging
from pathlib import Path

from mirage.adapter.media import extract_rms_envelope, probe_audio, probe_video
from mirage.adapter.media.video_decode import Frame, VideoReader
from mirage.adapter.vision.mediapipe_face import FaceExtractor, FaceTrack
from mirage.metrics.face_metrics import FaceMetrics, compute_face_metrics
from mirage.metrics.status import StatusResult, compute_status_badge
from mirage.metrics.video_quality import VideoQualityMetrics, compute_video_quality
from mirage.models.types import MetricBundleV1

logger = logging.getLogger(__name__)

# Module-level face extractor for reuse (avoids reinit overhead)
_face_extractor: FaceExtractor | None = None


def _get_face_extractor() -> FaceExtractor:
    """Get or create the shared FaceExtractor instance."""
    global _face_extractor
    if _face_extractor is None:
        _face_extractor = FaceExtractor()
    return _face_extractor


def _default_face_metrics() -> FaceMetrics:
    """Return default face metrics for failed decode."""
    return FaceMetrics(
        face_present_ratio=0.0,
        face_bbox_jitter=0.0,
        landmark_jitter=0.0,
        mouth_open_energy=0.0,
        mouth_audio_corr=0.0,
        blink_count=None,
        blink_rate_hz=None,
    )


def compute_metrics(video_path: Path, audio_path: Path) -> MetricBundleV1:
    """Compute complete MetricBundleV1 from canonical video and audio.

    This is the main entry point per IMPLEMENTATION_PLAN.md interface spec:
        def compute_metrics(canon_path: Path, audio_path: Path) -> MetricBundleV1

    Orchestrates adapters for IO, passes domain types to pure metric functions.
    Video is decoded once and reused for both video quality and face metrics.

    Args:
        video_path: Path to canonical video file.
        audio_path: Path to canonical audio file.

    Returns:
        Complete MetricBundleV1 with all metrics and status.
    """
    # Step 1: Probe A/V metadata via adapters
    video_duration_ms = 0
    audio_duration_ms = 0
    fps = 0.0

    try:
        video_info = probe_video(video_path)
        video_duration_ms = video_info.duration_ms
        fps = video_info.fps
    except (FileNotFoundError, RuntimeError):
        pass

    if audio_path.exists():
        try:
            audio_info = probe_audio(audio_path)
            audio_duration_ms = audio_info.duration_ms
        except (FileNotFoundError, RuntimeError):
            pass

    # Step 2: Decode video frames (once, reuse for all metrics)
    frames: list[Frame] = []
    frame_size: tuple[int, int] = (320, 240)  # Default

    try:
        with VideoReader(video_path) as reader:
            frames = list(reader.iter_frames())
            if reader.width > 0 and reader.height > 0:
                frame_size = (reader.width, reader.height)
    except (FileNotFoundError, RuntimeError):
        pass

    # Extract BGR arrays for video quality metrics
    bgr_frames = [f.bgr for f in frames]

    # Step 3: Compute video quality metrics (pure computation)
    video_quality: VideoQualityMetrics = compute_video_quality(
        frames=bgr_frames,
        video_duration_ms=video_duration_ms,
        audio_duration_ms=audio_duration_ms,
        fps=fps,
    )

    # Step 4: Compute face metrics (if decode successful)
    face_track: FaceTrack | None = None
    if video_quality.decode_ok and len(frames) > 0:
        # Extract face data via adapter (returns FaceTrack domain object)
        extractor = _get_face_extractor()
        face_track = extractor.extract_from_frames(frames, fps=fps)

        # Extract audio envelope via adapter
        try:
            audio_envelope = extract_rms_envelope(audio_path, fps=fps, num_frames=len(frames))
        except (FileNotFoundError, Exception):
            audio_envelope = [0.0] * len(frames)

        # Compute face metrics (pure computation on domain objects)
        face_metrics: FaceMetrics = compute_face_metrics(face_track, frame_size, audio_envelope)
    else:
        face_metrics = _default_face_metrics()

    # Step 4b: Compute SyncNet metrics (Tier 2, optional)
    lse_d: float | None = None
    lse_c: float | None = None

    if video_quality.decode_ok and len(frames) > 0 and audio_path.exists():
        try:
            from mirage.adapter.syncnet import compute_lse_metrics

            # Get face boxes from face_track if available
            face_boxes: list[list[float]] | None = None
            if face_track is not None:
                face_boxes = [fd.bbox for fd in face_track.face_data if fd.detected]

            # Compute LSE-D and LSE-C
            bgr_frames = [f.bgr for f in frames]
            lse_d, lse_c = compute_lse_metrics(
                bgr_frames, audio_path, fps=fps, face_boxes=face_boxes
            )

            if lse_d is not None:
                logger.info(f"SyncNet metrics: LSE-D={lse_d:.3f}, LSE-C={lse_c:.3f}")
        except Exception as e:
            logger.debug(f"SyncNet metrics unavailable: {e}")

    # Step 5: Compute status badge
    status: StatusResult = compute_status_badge(
        decode_ok=video_quality.decode_ok,
        face_present_ratio=face_metrics.face_present_ratio,
        av_duration_delta_ms=video_quality.av_duration_delta_ms,
        flicker_score=video_quality.flicker_score,
        freeze_frame_ratio=video_quality.freeze_frame_ratio,
        blur_score=video_quality.blur_score,
        mouth_audio_corr=face_metrics.mouth_audio_corr,
    )

    # Step 6: Assemble MetricBundleV1
    return MetricBundleV1(
        # Video quality metrics
        decode_ok=video_quality.decode_ok,
        video_duration_ms=video_quality.video_duration_ms,
        audio_duration_ms=video_quality.audio_duration_ms,
        av_duration_delta_ms=video_quality.av_duration_delta_ms,
        fps=video_quality.fps,
        frame_count=video_quality.frame_count,
        scene_cut_count=video_quality.scene_cut_count,
        freeze_frame_ratio=video_quality.freeze_frame_ratio,
        flicker_score=video_quality.flicker_score,
        blur_score=video_quality.blur_score,
        frame_diff_spike_count=video_quality.frame_diff_spike_count,
        # Face metrics
        face_present_ratio=face_metrics.face_present_ratio,
        face_bbox_jitter=face_metrics.face_bbox_jitter,
        landmark_jitter=face_metrics.landmark_jitter,
        mouth_open_energy=face_metrics.mouth_open_energy,
        mouth_audio_corr=face_metrics.mouth_audio_corr,
        blink_count=face_metrics.blink_count,
        blink_rate_hz=face_metrics.blink_rate_hz,
        # SyncNet metrics (Tier 2, optional)
        lse_d=lse_d,
        lse_c=lse_c,
        # Status
        status_badge=status.badge,
        reasons=status.reasons,
    )
