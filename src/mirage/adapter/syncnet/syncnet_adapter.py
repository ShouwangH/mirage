"""Lip-sync evaluation adapter.

Computes LSE-D (Lip Sync Error Distance) and LSE-C (Lip Sync Error Confidence)
metrics using correlation between mouth movement and audio energy.

This implementation uses a correlation-based approach:
- LSE-D: Inverted correlation scaled to match typical SyncNet range (lower = better)
- LSE-C: Confidence based on correlation strength (higher = better)

Typical good values: LSE-D < 8, LSE-C > 3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Processing parameters
SAMPLE_RATE = 16000
VIDEO_FPS = 25


@dataclass
class SyncNetResult:
    """Result of lip sync evaluation.

    Attributes:
        lse_d: Lip Sync Error Distance (lower = better sync).
        lse_c: Lip Sync Error Confidence (higher = more confident).
        offset: Detected A/V offset in frames.
    """

    lse_d: float
    lse_c: float
    offset: int


def _extract_audio_energy(
    audio_path: Path, num_frames: int, fps: float = VIDEO_FPS
) -> "NDArray[np.float32]" | None:
    """Extract audio energy envelope aligned to video frames.

    Args:
        audio_path: Path to audio file.
        num_frames: Number of video frames.
        fps: Video frame rate.

    Returns:
        Audio energy array of shape (num_frames,), or None on failure.
    """
    try:
        import librosa
    except ImportError:
        logger.warning("librosa not available for audio extraction")
        return None

    try:
        # Load audio
        audio, sr = librosa.load(str(audio_path), sr=SAMPLE_RATE)

        # Compute RMS energy per frame
        samples_per_frame = int(SAMPLE_RATE / fps)
        energy = []

        for i in range(num_frames):
            start = i * samples_per_frame
            end = start + samples_per_frame
            if end <= len(audio):
                frame_audio = audio[start:end]
                rms = np.sqrt(np.mean(frame_audio**2))
                energy.append(rms)
            else:
                energy.append(0.0)

        return np.array(energy, dtype=np.float32)

    except Exception as e:
        logger.warning(f"Audio energy extraction failed: {e}")
        return None


def _extract_mouth_movement(
    frames: list["NDArray[np.uint8]"],
    face_boxes: list[list[float]] | None = None,
) -> "NDArray[np.float32]" | None:
    """Extract mouth movement signal from video frames.

    Uses optical flow in the mouth region to estimate movement.

    Args:
        frames: List of BGR frames.
        face_boxes: Optional face bounding boxes per frame.

    Returns:
        Mouth movement array of shape (num_frames,), or None on failure.
    """
    try:
        import cv2
    except ImportError:
        return None

    if len(frames) < 2:
        return None

    movement = [0.0]  # First frame has no movement

    for i in range(1, len(frames)):
        prev_frame = frames[i - 1]
        curr_frame = frames[i]

        h, w = prev_frame.shape[:2]

        # Get mouth region (lower third of face area)
        if face_boxes and i < len(face_boxes) and len(face_boxes[i]) >= 4:
            x1, y1, x2, y2 = [int(v) for v in face_boxes[i][:4]]
            # Lower third is mouth area
            mouth_y1 = y1 + int((y2 - y1) * 0.6)
            mouth_region_prev = prev_frame[mouth_y1:y2, x1:x2]
            mouth_region_curr = curr_frame[mouth_y1:y2, x1:x2]
        else:
            # Default: center-bottom region
            mouth_y1 = int(h * 0.5)
            mouth_x1, mouth_x2 = int(w * 0.25), int(w * 0.75)
            mouth_region_prev = prev_frame[mouth_y1:, mouth_x1:mouth_x2]
            mouth_region_curr = curr_frame[mouth_y1:, mouth_x1:mouth_x2]

        if mouth_region_prev.size == 0 or mouth_region_curr.size == 0:
            movement.append(0.0)
            continue

        # Convert to grayscale
        gray_prev = cv2.cvtColor(mouth_region_prev, cv2.COLOR_BGR2GRAY)
        gray_curr = cv2.cvtColor(mouth_region_curr, cv2.COLOR_BGR2GRAY)

        # Ensure same size
        if gray_prev.shape != gray_curr.shape:
            movement.append(0.0)
            continue

        # Compute frame difference as movement proxy
        diff = cv2.absdiff(gray_prev, gray_curr)
        mean_diff = np.mean(diff)
        movement.append(float(mean_diff))

    return np.array(movement, dtype=np.float32)


def _compute_correlation_with_lag(
    signal1: "NDArray[np.float32]",
    signal2: "NDArray[np.float32]",
    max_lag: int = 5,
) -> tuple[float, int]:
    """Compute best correlation between two signals with lag search.

    Args:
        signal1: First signal.
        signal2: Second signal.
        max_lag: Maximum lag in frames to search.

    Returns:
        Tuple of (best_correlation, best_lag).
    """
    best_corr = -1.0
    best_lag = 0

    # Normalize signals
    s1 = signal1 - np.mean(signal1)
    s2 = signal2 - np.mean(signal2)

    std1 = np.std(s1)
    std2 = np.std(s2)

    if std1 < 1e-6 or std2 < 1e-6:
        return 0.0, 0

    s1 = s1 / std1
    s2 = s2 / std2

    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            s1_slice = s1[lag:]
            s2_slice = s2[: len(s1) - lag]
        else:
            s1_slice = s1[: len(s1) + lag]
            s2_slice = s2[-lag:]

        if len(s1_slice) < 10:
            continue

        corr = np.mean(s1_slice * s2_slice)

        if corr > best_corr:
            best_corr = corr
            best_lag = lag

    return float(best_corr), best_lag


class SyncNetEvaluator:
    """Lip sync evaluator using correlation-based approach."""

    def __init__(self) -> None:
        """Initialize evaluator."""
        pass

    def evaluate(
        self,
        frames: list["NDArray[np.uint8]"],
        audio_path: Path,
        fps: float = VIDEO_FPS,
        face_boxes: list[list[float]] | None = None,
    ) -> SyncNetResult | None:
        """Evaluate lip sync quality.

        Args:
            frames: List of BGR video frames.
            audio_path: Path to audio file.
            fps: Video frame rate.
            face_boxes: Optional face bounding boxes per frame.

        Returns:
            SyncNetResult with LSE-D, LSE-C, and offset, or None if evaluation fails.
        """
        if len(frames) < 10:
            logger.warning("Not enough frames for lip sync evaluation")
            return None

        # Extract audio energy
        audio_energy = _extract_audio_energy(audio_path, len(frames), fps)
        if audio_energy is None:
            return None

        # Extract mouth movement
        mouth_movement = _extract_mouth_movement(frames, face_boxes)
        if mouth_movement is None:
            return None

        # Compute correlation with lag search
        corr, lag = _compute_correlation_with_lag(mouth_movement, audio_energy)

        # Convert correlation to LSE-D and LSE-C
        # LSE-D: lower is better, typical range 5-10
        # corr ranges from -1 to 1, we map to ~5-15
        lse_d = 10.0 - (corr * 5.0)  # corr=1 -> 5, corr=0 -> 10, corr=-1 -> 15

        # LSE-C: higher is better, typical range 3-8
        # Based on correlation strength
        lse_c = max(0.0, corr * 8.0)  # corr=1 -> 8, corr=0 -> 0

        return SyncNetResult(lse_d=lse_d, lse_c=lse_c, offset=lag)


# Module-level evaluator instance
_evaluator: SyncNetEvaluator | None = None


def get_evaluator() -> SyncNetEvaluator:
    """Get or create the shared evaluator."""
    global _evaluator
    if _evaluator is None:
        _evaluator = SyncNetEvaluator()
    return _evaluator


def compute_lse_metrics(
    frames: list["NDArray[np.uint8]"],
    audio_path: Path,
    fps: float = VIDEO_FPS,
    face_boxes: list[list[float]] | None = None,
) -> tuple[float | None, float | None]:
    """Compute LSE-D and LSE-C metrics.

    Convenience function that uses the shared evaluator.

    Args:
        frames: List of BGR video frames.
        audio_path: Path to audio file.
        fps: Video frame rate.
        face_boxes: Optional face bounding boxes per frame.

    Returns:
        Tuple of (lse_d, lse_c), or (None, None) if evaluation fails.
    """
    evaluator = get_evaluator()
    result = evaluator.evaluate(frames, audio_path, fps, face_boxes)
    if result is None:
        return None, None
    return result.lse_d, result.lse_c
