"""Video quality metrics - pure computations on frame data.

Metrics from METRICS.md:
- freeze_frame_ratio: ratio of frozen frames
- flicker_score: luminance instability
- blur_score: variance of Laplacian (higher = sharper)
- scene_cut_count: abrupt scene changes
- frame_diff_spike_count: glitch detection

This module contains ONLY pure computations on numpy arrays.
Video decoding and probing are done by adapters called from bundle.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Thresholds for metric computation
FREEZE_EPSILON = 1.0  # Mean absolute diff below this = frozen
SCENE_CUT_THRESHOLD = 0.5  # Histogram chi-squared diff threshold for scene cut
SPIKE_SIGMA = 3.0  # Frames with diff > mean + SPIKE_SIGMA * std are spikes


@dataclass
class VideoQualityMetrics:
    """Result of video quality metric computation.

    All metrics are computed from frame arrays.
    """

    decode_ok: bool
    video_duration_ms: int
    audio_duration_ms: int
    av_duration_delta_ms: int
    fps: float
    frame_count: int
    scene_cut_count: int
    freeze_frame_ratio: float
    flicker_score: float
    blur_score: float
    frame_diff_spike_count: int


def compute_freeze_frame_ratio(frames: list[np.ndarray]) -> float:
    """Compute ratio of frozen (nearly identical) consecutive frames.

    Args:
        frames: List of numpy array frames (BGR).

    Returns:
        Ratio in [0, 1], where 1 = all frames frozen.
    """
    if len(frames) < 2:
        return 0.0

    freeze_count = 0
    for i in range(1, len(frames)):
        diff = np.abs(frames[i].astype(float) - frames[i - 1].astype(float))
        mean_diff = np.mean(diff)
        if mean_diff < FREEZE_EPSILON:
            freeze_count += 1

    return freeze_count / (len(frames) - 1)


def compute_flicker_score(frames: list[np.ndarray]) -> float:
    """Compute flicker score based on luminance instability.

    Higher score = more flicker.

    Args:
        frames: List of numpy array frames (BGR).

    Returns:
        Flicker score (stddev of mean luminance).
    """
    if len(frames) < 2:
        return 0.0

    try:
        import cv2
    except ImportError:
        return 0.0

    luminances = []
    for frame in frames:
        # Convert to grayscale for luminance
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        luminances.append(np.mean(gray))

    return float(np.std(luminances))


def compute_blur_score(frames: list[np.ndarray]) -> float:
    """Compute blur score using variance of Laplacian.

    Higher score = sharper image (less blur).

    Args:
        frames: List of numpy array frames (BGR).

    Returns:
        Mean variance of Laplacian across frames.
    """
    if len(frames) == 0:
        return 0.0

    try:
        import cv2
    except ImportError:
        return 0.0

    variances = []
    for frame in frames:
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variances.append(laplacian.var())

    return float(np.mean(variances))


def compute_scene_cuts(frames: list[np.ndarray]) -> int:
    """Detect scene cuts using histogram difference.

    Args:
        frames: List of numpy array frames (BGR).

    Returns:
        Number of detected scene cuts.
    """
    if len(frames) < 2:
        return 0

    try:
        import cv2
    except ImportError:
        return 0

    cuts = 0
    prev_hist = None

    for frame in frames:
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()  # Normalize

        if prev_hist is not None:
            # Chi-squared distance
            diff = np.sum((hist - prev_hist) ** 2 / (hist + prev_hist + 1e-10))
            if diff > SCENE_CUT_THRESHOLD:
                cuts += 1

        prev_hist = hist

    return cuts


def compute_frame_diff_spikes(frames: list[np.ndarray]) -> int:
    """Detect frames with abnormally high difference from previous.

    Args:
        frames: List of numpy array frames (BGR).

    Returns:
        Number of spike frames (potential glitches).
    """
    if len(frames) < 2:
        return 0

    diffs = []
    for i in range(1, len(frames)):
        diff = np.mean(np.abs(frames[i].astype(float) - frames[i - 1].astype(float)))
        diffs.append(diff)

    if len(diffs) == 0:
        return 0

    diffs_arr = np.array(diffs)
    mean_diff = np.mean(diffs_arr)
    std_diff = np.std(diffs_arr)

    if std_diff == 0:
        return 0

    threshold = mean_diff + SPIKE_SIGMA * std_diff
    return int(np.sum(diffs_arr > threshold))


def compute_video_quality(
    frames: list[np.ndarray],
    video_duration_ms: int,
    audio_duration_ms: int,
    fps: float,
) -> VideoQualityMetrics:
    """Compute all video quality metrics from frames.

    This is a pure computation function - video decoding and probing
    are done by adapters in bundle.py.

    Args:
        frames: List of BGR numpy arrays from video.
        video_duration_ms: Video duration in milliseconds.
        audio_duration_ms: Audio duration in milliseconds.
        fps: Video frame rate.

    Returns:
        VideoQualityMetrics with all computed values.
    """
    decode_ok = len(frames) > 0

    if not decode_ok:
        return VideoQualityMetrics(
            decode_ok=False,
            video_duration_ms=video_duration_ms,
            audio_duration_ms=audio_duration_ms,
            av_duration_delta_ms=abs(video_duration_ms - audio_duration_ms),
            fps=fps,
            frame_count=0,
            scene_cut_count=0,
            freeze_frame_ratio=0.0,
            flicker_score=0.0,
            blur_score=0.0,
            frame_diff_spike_count=0,
        )

    return VideoQualityMetrics(
        decode_ok=True,
        video_duration_ms=video_duration_ms,
        audio_duration_ms=audio_duration_ms,
        av_duration_delta_ms=abs(video_duration_ms - audio_duration_ms),
        fps=fps,
        frame_count=len(frames),
        scene_cut_count=compute_scene_cuts(frames),
        freeze_frame_ratio=compute_freeze_frame_ratio(frames),
        flicker_score=compute_flicker_score(frames),
        blur_score=compute_blur_score(frames),
        frame_diff_spike_count=compute_frame_diff_spikes(frames),
    )
