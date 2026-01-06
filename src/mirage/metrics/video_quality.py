"""Video quality metrics using opencv/numpy.

Metrics from METRICS.md:
- decode_ok: video can be decoded and has >= 1 frame
- video_duration_ms, audio_duration_ms, av_duration_delta_ms
- fps, frame_count
- scene_cut_count: abrupt scene changes
- freeze_frame_ratio: ratio of frozen frames
- flicker_score: luminance instability
- blur_score: variance of Laplacian (higher = sharper)
- frame_diff_spike_count: glitch detection

Note: This module uses cv2/numpy for image processing transforms (grayscale,
histogram, laplacian). These are deterministic array operations and belong
in the metrics layer, not adapters. Video file IO uses adapter/media/.
"""

from __future__ import annotations

from pathlib import Path

from mirage.adapter.media import probe_audio, probe_video
from mirage.adapter.media.video_decode import VideoReader

# Thresholds for metric computation
FREEZE_EPSILON = 1.0  # Mean absolute diff below this = frozen
SCENE_CUT_THRESHOLD = 0.5  # Histogram chi-squared diff threshold for scene cut
SPIKE_SIGMA = 3.0  # Frames with diff > mean + SPIKE_SIGMA * std are spikes


def get_av_info(video_path: Path, audio_path: Path) -> dict:
    """Get audio/video duration and fps info.

    Args:
        video_path: Path to video file.
        audio_path: Path to audio file.

    Returns:
        Dict with video_duration_ms, audio_duration_ms, av_duration_delta_ms,
        fps, frame_count.

    Raises:
        FileNotFoundError: If video file doesn't exist.
        RuntimeError: If probe fails or times out.
    """
    # Get video info via adapter
    video_info = probe_video(video_path)

    # Get audio duration
    audio_duration_ms = 0
    if audio_path.exists():
        try:
            audio_info = probe_audio(audio_path)
            audio_duration_ms = audio_info.duration_ms
        except RuntimeError:
            pass  # Audio probe failed, use 0

    return {
        "video_duration_ms": video_info.duration_ms,
        "audio_duration_ms": audio_duration_ms,
        "av_duration_delta_ms": abs(video_info.duration_ms - audio_duration_ms),
        "fps": video_info.fps,
        "frame_count": video_info.frame_count,
    }


def decode_video(video_path: Path, max_frames: int = 0) -> list:
    """Decode video frames via adapter.

    Args:
        video_path: Path to video file.
        max_frames: Maximum frames to decode (0 = all).

    Returns:
        List of numpy arrays (BGR frames), empty if decode fails.
    """
    if not video_path.exists():
        return []

    try:
        with VideoReader(video_path) as reader:
            frames = list(
                reader.iter_frames(max_frames=max_frames if max_frames > 0 else None)
            )
            return [f.bgr for f in frames]
    except (FileNotFoundError, RuntimeError):
        return []


def compute_freeze_frame_ratio(frames: list) -> float:
    """Compute ratio of frozen (nearly identical) consecutive frames.

    Args:
        frames: List of numpy array frames.

    Returns:
        Ratio in [0, 1], where 1 = all frames frozen.
    """
    if len(frames) < 2:
        return 0.0

    try:
        import numpy as np
    except ImportError:
        return 0.0

    freeze_count = 0
    for i in range(1, len(frames)):
        diff = np.abs(frames[i].astype(float) - frames[i - 1].astype(float))
        mean_diff = np.mean(diff)
        if mean_diff < FREEZE_EPSILON:
            freeze_count += 1

    return freeze_count / (len(frames) - 1)


def compute_flicker_score(frames: list) -> float:
    """Compute flicker score based on luminance instability.

    Higher score = more flicker.

    Args:
        frames: List of numpy array frames.

    Returns:
        Flicker score (stddev of mean luminance).
    """
    if len(frames) < 2:
        return 0.0

    try:
        import cv2
        import numpy as np
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


def compute_blur_score(frames: list) -> float:
    """Compute blur score using variance of Laplacian.

    Higher score = sharper image (less blur).

    Args:
        frames: List of numpy array frames.

    Returns:
        Mean variance of Laplacian across frames.
    """
    if len(frames) == 0:
        return 0.0

    try:
        import cv2
        import numpy as np
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


def compute_scene_cuts(frames: list) -> int:
    """Detect scene cuts using histogram difference.

    Args:
        frames: List of numpy array frames.

    Returns:
        Number of detected scene cuts.
    """
    if len(frames) < 2:
        return 0

    try:
        import cv2
        import numpy as np
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


def compute_frame_diff_spikes(frames: list) -> int:
    """Detect frames with abnormally high difference from previous.

    Args:
        frames: List of numpy array frames.

    Returns:
        Number of spike frames (potential glitches).
    """
    if len(frames) < 2:
        return 0

    try:
        import numpy as np
    except ImportError:
        return 0

    diffs = []
    for i in range(1, len(frames)):
        diff = np.mean(np.abs(frames[i].astype(float) - frames[i - 1].astype(float)))
        diffs.append(diff)

    if len(diffs) == 0:
        return 0

    diffs = np.array(diffs)
    mean_diff = np.mean(diffs)
    std_diff = np.std(diffs)

    if std_diff == 0:
        return 0

    threshold = mean_diff + SPIKE_SIGMA * std_diff
    return int(np.sum(diffs > threshold))


def compute_video_quality_metrics(video_path: Path, audio_path: Path) -> dict:
    """Compute all Tier 0 metrics.

    Args:
        video_path: Path to canonical video.
        audio_path: Path to canonical audio.

    Returns:
        Dict with all Tier 0 metric fields.
    """
    # Initialize with failure defaults
    metrics = {
        "decode_ok": False,
        "video_duration_ms": 0,
        "audio_duration_ms": 0,
        "av_duration_delta_ms": 0,
        "fps": 0.0,
        "frame_count": 0,
        "scene_cut_count": 0,
        "freeze_frame_ratio": 0.0,
        "flicker_score": 0.0,
        "blur_score": 0.0,
        "frame_diff_spike_count": 0,
    }

    # Try to get A/V info
    try:
        av_info = get_av_info(video_path, audio_path)
        metrics.update(av_info)
    except (FileNotFoundError, RuntimeError):
        return metrics

    # Try to decode video
    frames = decode_video(video_path)
    if len(frames) == 0:
        return metrics

    # Decode succeeded
    metrics["decode_ok"] = True
    metrics["frame_count"] = len(frames)

    # Compute frame-based metrics
    metrics["freeze_frame_ratio"] = compute_freeze_frame_ratio(frames)
    metrics["flicker_score"] = compute_flicker_score(frames)
    metrics["blur_score"] = compute_blur_score(frames)
    metrics["scene_cut_count"] = compute_scene_cuts(frames)
    metrics["frame_diff_spike_count"] = compute_frame_diff_spikes(frames)

    return metrics
