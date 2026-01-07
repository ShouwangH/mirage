"""Face metrics - pure computations on FaceTrack data.

Metrics from METRICS.md:
- face_present_ratio: % frames with detected face
- face_bbox_jitter: bbox stability (normalized by frame size)
- landmark_jitter: landmark stability (normalized by inter-ocular distance)
- mouth_open_energy: variance of mouth openness
- mouth_audio_corr: correlation between mouth and audio envelope
- blink_count, blink_rate_hz: blink detection via eye aspect ratio

This module contains ONLY pure computations on domain data.
Face detection is handled by adapter/vision/mediapipe_face.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mirage.adapter.vision.mediapipe_face import FaceData, FaceTrack

# Landmark indices for derived computations
# Upper lip: 13, Lower lip: 14 (simplified)
UPPER_LIP_IDX = 13
LOWER_LIP_IDX = 14
# Eye landmarks for EAR (Eye Aspect Ratio)
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
# Inter-ocular landmarks for normalization
LEFT_EYE_CENTER = 33
RIGHT_EYE_CENTER = 263

# Thresholds for blink detection
# Note: With blendshapes, eye_open ranges from 0 (closed) to 1 (open)
# Traditional EAR threshold of 0.2 is too strict for blendshape values
# A value of 0.5 indicates eye is half-closed, good indicator of blink
EYE_BLINK_THRESHOLD = 0.5  # Below this = potential blink
BLINK_CONSEC_FRAMES = 1  # Minimum frames for a blink (blendshapes are smoother)


@dataclass
class FaceMetrics:
    """Result of face metric computation.

    All metrics are computed from FaceTrack domain data.
    """

    face_present_ratio: float
    face_bbox_jitter: float
    landmark_jitter: float
    mouth_open_energy: float
    mouth_audio_corr: float
    blink_count: int | None
    blink_rate_hz: float | None


def _compute_mouth_openness_from_landmarks(landmarks: list[list[float]]) -> float:
    """Compute mouth openness from landmarks (fallback method).

    Args:
        landmarks: List of [x, y] normalized landmark coordinates.

    Returns:
        Mouth openness value (distance between lips).
    """
    if len(landmarks) < max(UPPER_LIP_IDX, LOWER_LIP_IDX) + 1:
        return 0.0

    upper = landmarks[UPPER_LIP_IDX]
    lower = landmarks[LOWER_LIP_IDX]

    return math.sqrt((upper[0] - lower[0]) ** 2 + (upper[1] - lower[1]) ** 2)


def _compute_eye_aspect_ratio(landmarks: list[list[float]]) -> float:
    """Compute eye aspect ratio for blink detection.

    Args:
        landmarks: List of [x, y] normalized landmark coordinates.

    Returns:
        Average eye aspect ratio (lower = more closed).
    """
    if len(landmarks) < max(max(LEFT_EYE_INDICES), max(RIGHT_EYE_INDICES)) + 1:
        return 0.3  # Default open eye

    def ear_for_eye(indices: list[int]) -> float:
        # Simplified EAR: vertical distance / horizontal distance
        p1 = landmarks[indices[1]]
        p2 = landmarks[indices[5]]
        p3 = landmarks[indices[2]]
        p4 = landmarks[indices[4]]
        p5 = landmarks[indices[0]]
        p6 = landmarks[indices[3]]

        # Vertical distances
        v1 = math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)
        v2 = math.sqrt((p4[0] - p3[0]) ** 2 + (p4[1] - p3[1]) ** 2)

        # Horizontal distance
        h = math.sqrt((p6[0] - p5[0]) ** 2 + (p6[1] - p5[1]) ** 2)

        if h == 0:
            return 0.3

        return (v1 + v2) / (2.0 * h)

    left_ear = ear_for_eye(LEFT_EYE_INDICES)
    right_ear = ear_for_eye(RIGHT_EYE_INDICES)

    return (left_ear + right_ear) / 2.0


def _compute_face_present_ratio(face_track: "FaceTrack") -> float:
    """Compute ratio of frames with detected face.

    Args:
        face_track: FaceTrack with detection results.

    Returns:
        Ratio in [0, 1].
    """
    if face_track.frame_count == 0:
        return 0.0

    face_count = sum(1 for fd in face_track.face_data if fd.detected)
    return face_count / face_track.frame_count


def _compute_face_bbox_jitter(face_track: "FaceTrack", frame_size: tuple[int, int]) -> float:
    """Compute bounding box jitter (normalized by frame size).

    Args:
        face_track: FaceTrack with detection results.
        frame_size: (width, height) of frames.

    Returns:
        Average normalized bbox movement between frames.
    """
    if face_track.frame_count < 2:
        return 0.0

    w, h = frame_size
    norm_factor = math.sqrt(w * w + h * h)

    movements = []
    prev_bbox: list[float] | None = None

    for fd in face_track.face_data:
        if not fd.detected or len(fd.bbox) < 4:
            prev_bbox = None
            continue

        bbox = fd.bbox
        if prev_bbox is not None:
            # Compute center movement
            cx1 = (prev_bbox[0] + prev_bbox[2]) / 2
            cy1 = (prev_bbox[1] + prev_bbox[3]) / 2
            cx2 = (bbox[0] + bbox[2]) / 2
            cy2 = (bbox[1] + bbox[3]) / 2

            # Compute size change
            w1 = prev_bbox[2] - prev_bbox[0]
            h1 = prev_bbox[3] - prev_bbox[1]
            w2 = bbox[2] - bbox[0]
            h2 = bbox[3] - bbox[1]

            center_dist = math.sqrt((cx2 - cx1) ** 2 + (cy2 - cy1) ** 2)
            size_dist = math.sqrt((w2 - w1) ** 2 + (h2 - h1) ** 2)

            movements.append((center_dist + size_dist) / norm_factor)

        prev_bbox = bbox

    if len(movements) == 0:
        return 0.0

    return sum(movements) / len(movements)


def _compute_landmark_jitter(face_track: "FaceTrack") -> float:
    """Compute landmark jitter (normalized by inter-ocular distance).

    Args:
        face_track: FaceTrack with detection results.

    Returns:
        Average normalized landmark movement.
    """
    if face_track.frame_count < 2:
        return 0.0

    movements = []
    prev_landmarks: list[list[float]] | None = None
    prev_iod: float | None = None

    for fd in face_track.face_data:
        if not fd.detected or len(fd.landmarks) == 0:
            prev_landmarks = None
            prev_iod = None
            continue

        landmarks = fd.landmarks

        # Compute inter-ocular distance for normalization
        if len(landmarks) > max(LEFT_EYE_CENTER, RIGHT_EYE_CENTER):
            left = landmarks[LEFT_EYE_CENTER]
            right = landmarks[RIGHT_EYE_CENTER]
            iod = math.sqrt((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2)
        else:
            iod = 0.1  # Default

        if prev_landmarks is not None and prev_iod is not None and prev_iod > 0:
            # Compute average L2 displacement
            total_disp = 0.0
            count = min(len(landmarks), len(prev_landmarks))
            for i in range(count):
                dx = landmarks[i][0] - prev_landmarks[i][0]
                dy = landmarks[i][1] - prev_landmarks[i][1]
                total_disp += math.sqrt(dx * dx + dy * dy)

            if count > 0:
                avg_disp = total_disp / count
                movements.append(avg_disp / prev_iod)

        prev_landmarks = landmarks
        prev_iod = iod

    if len(movements) == 0:
        return 0.0

    return sum(movements) / len(movements)


def _get_mouth_openness(fd: "FaceData") -> float:
    """Get mouth openness from FaceData, preferring blendshape value.

    Args:
        fd: FaceData with detection results.

    Returns:
        Mouth openness value (0-1 from blendshapes, or landmark distance as fallback).
    """
    # Prefer blendshape value (more accurate)
    if fd.mouth_open > 0:
        return fd.mouth_open

    # Fallback to landmark-based computation
    if len(fd.landmarks) > 0:
        return _compute_mouth_openness_from_landmarks(fd.landmarks)

    return 0.0


def _compute_mouth_open_energy(face_track: "FaceTrack") -> float:
    """Compute variance of mouth openness over time.

    Args:
        face_track: FaceTrack with detection results.

    Returns:
        Variance of mouth openness (higher = more movement).
    """
    openness_values = []
    for fd in face_track.face_data:
        if fd.detected:
            openness = _get_mouth_openness(fd)
            openness_values.append(openness)

    if len(openness_values) < 2:
        return 0.0

    mean_val = sum(openness_values) / len(openness_values)
    variance = sum((v - mean_val) ** 2 for v in openness_values) / len(openness_values)

    return variance


def _compute_mouth_audio_corr(face_track: "FaceTrack", audio_envelope: list[float]) -> float:
    """Compute correlation between mouth openness and audio envelope.

    Args:
        face_track: FaceTrack with detection results.
        audio_envelope: Audio RMS envelope per frame.

    Returns:
        Correlation coefficient in [-1, 1], or 0 if cannot compute.
    """
    try:
        import numpy as np
    except ImportError:
        return 0.0

    if face_track.frame_count == 0 or len(audio_envelope) == 0:
        return 0.0

    # Extract mouth openness values
    mouth_values = []
    for fd in face_track.face_data:
        if fd.detected:
            mouth_values.append(_get_mouth_openness(fd))
        else:
            mouth_values.append(0.0)

    mouth_arr = np.array(mouth_values)
    audio_arr = np.array(audio_envelope)

    # Align lengths
    min_len = min(len(mouth_arr), len(audio_arr))
    if min_len < 2:
        return 0.0

    mouth_arr = mouth_arr[:min_len]
    audio_arr = audio_arr[:min_len]

    # Compute correlation
    mouth_std = np.std(mouth_arr)
    audio_std = np.std(audio_arr)

    if mouth_std == 0 or audio_std == 0:
        return 0.0

    corr = np.corrcoef(mouth_arr, audio_arr)[0, 1]

    if np.isnan(corr):
        return 0.0

    return float(corr)


def _get_eye_openness(fd: "FaceData") -> float:
    """Get average eye openness from FaceData, preferring blendshape values.

    Args:
        fd: FaceData with detection results.

    Returns:
        Eye openness value (0 = closed, 1 = open).
    """
    # Check if blendshape values are available (not default 1.0)
    if fd.left_eye_open < 1.0 or fd.right_eye_open < 1.0:
        return (fd.left_eye_open + fd.right_eye_open) / 2.0

    # Fallback to landmark-based EAR computation
    if len(fd.landmarks) > 0:
        return _compute_eye_aspect_ratio(fd.landmarks)

    return 0.3  # Default open


def _compute_blink_metrics(face_track: "FaceTrack") -> tuple[int | None, float | None]:
    """Detect blinks using eye openness (blendshapes or EAR).

    Args:
        face_track: FaceTrack with detection results.

    Returns:
        Tuple of (blink_count, blink_rate_hz), or (None, None) if insufficient data.
    """
    if face_track.frame_count == 0 or face_track.fps <= 0:
        return None, None

    # Extract eye openness values
    eye_values = []
    for fd in face_track.face_data:
        if fd.detected:
            eye_values.append(_get_eye_openness(fd))
        else:
            eye_values.append(0.3)  # Default open

    # Detect blinks (eye openness below threshold for consecutive frames)
    blink_count = 0
    blink_frames = 0

    for eye_open in eye_values:
        if eye_open < EYE_BLINK_THRESHOLD:
            blink_frames += 1
        else:
            if blink_frames >= BLINK_CONSEC_FRAMES:
                blink_count += 1
            blink_frames = 0

    # Check for blink at end
    if blink_frames >= BLINK_CONSEC_FRAMES:
        blink_count += 1

    # Compute rate
    duration_sec = face_track.frame_count / face_track.fps
    if duration_sec > 0:
        blink_rate = blink_count / duration_sec
    else:
        blink_rate = 0.0

    return blink_count, blink_rate


def compute_face_metrics(
    face_track: "FaceTrack",
    frame_size: tuple[int, int],
    audio_envelope: list[float],
) -> FaceMetrics:
    """Compute all face metrics from FaceTrack.

    This is a pure computation function - face detection is done by
    adapter/vision/mediapipe_face and passed in as FaceTrack.

    Args:
        face_track: FaceTrack from FaceExtractor with detection results.
        frame_size: (width, height) of video frames for normalization.
        audio_envelope: Audio RMS envelope per frame from audio adapter.

    Returns:
        FaceMetrics with all computed values.
    """
    face_present_ratio = _compute_face_present_ratio(face_track)
    face_bbox_jitter = _compute_face_bbox_jitter(face_track, frame_size)
    landmark_jitter = _compute_landmark_jitter(face_track)
    mouth_open_energy = _compute_mouth_open_energy(face_track)
    mouth_audio_corr = _compute_mouth_audio_corr(face_track, audio_envelope)
    blink_count, blink_rate_hz = _compute_blink_metrics(face_track)

    return FaceMetrics(
        face_present_ratio=face_present_ratio,
        face_bbox_jitter=face_bbox_jitter,
        landmark_jitter=landmark_jitter,
        mouth_open_energy=mouth_open_energy,
        mouth_audio_corr=mouth_audio_corr,
        blink_count=blink_count,
        blink_rate_hz=blink_rate_hz,
    )
