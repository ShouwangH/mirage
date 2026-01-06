"""Face metrics - pure computations on face detection data.

Metrics from METRICS.md:
- face_present_ratio: % frames with detected face
- face_bbox_jitter: bbox stability (normalized by frame size)
- landmark_jitter: landmark stability (normalized by inter-ocular distance)
- mouth_open_energy: variance of mouth openness
- mouth_audio_corr: correlation between mouth and audio envelope
- blink_count, blink_rate_hz: blink detection via eye aspect ratio

Note: Face detection uses adapter/vision/mediapipe_face. This module contains
only pure computations on the detected landmarks/bboxes.
"""

from __future__ import annotations

import math

from mirage.adapter.vision import FaceExtractor

# Mediapipe face mesh landmark indices
# Upper lip: 13, Lower lip: 14 (simplified)
UPPER_LIP_IDX = 13
LOWER_LIP_IDX = 14
# Eye landmarks for EAR (Eye Aspect Ratio)
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
# Inter-ocular landmarks for normalization
LEFT_EYE_CENTER = 33
RIGHT_EYE_CENTER = 263

# Thresholds
EAR_THRESHOLD = 0.2  # Below this = blink
BLINK_CONSEC_FRAMES = 2  # Minimum frames for a blink

# Module-level extractor for reuse (avoids reinit overhead)
_extractor: FaceExtractor | None = None


def _get_extractor() -> FaceExtractor:
    """Get or create the shared FaceExtractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = FaceExtractor()
    return _extractor


def extract_face_data(frames: list, fps: float = 30.0) -> list:
    """Extract face detection data from frames via adapter.

    Args:
        frames: List of numpy array frames (BGR).
        fps: Video frame rate.

    Returns:
        List of face data dicts (or None if no face detected).
        Each dict contains: bbox, landmarks, mouth_openness, eye_aspect_ratio.
    """
    if len(frames) == 0:
        return []

    # Use adapter for face detection
    extractor = _get_extractor()
    track = extractor.extract_from_bgr_arrays(frames, fps=fps)

    # Convert FaceTrack to legacy dict format with derived values
    results = []
    for fd in track.face_data:
        if fd.detected and len(fd.landmarks) > 0:
            # Compute derived metrics from landmarks
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


def _compute_mouth_openness(landmarks: list) -> float:
    """Compute mouth openness from landmarks.

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


def _compute_eye_aspect_ratio(landmarks: list) -> float:
    """Compute eye aspect ratio for blink detection.

    Args:
        landmarks: List of [x, y] normalized landmark coordinates.

    Returns:
        Average eye aspect ratio (lower = more closed).
    """
    if len(landmarks) < max(max(LEFT_EYE_INDICES), max(RIGHT_EYE_INDICES)) + 1:
        return 0.3  # Default open eye

    def ear_for_eye(indices):
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


def compute_face_present_ratio(face_data: list) -> float:
    """Compute ratio of frames with detected face.

    Args:
        face_data: List of face data dicts (None if no face).

    Returns:
        Ratio in [0, 1].
    """
    if len(face_data) == 0:
        return 0.0

    face_count = sum(1 for f in face_data if f is not None)
    return face_count / len(face_data)


def compute_face_bbox_jitter(face_data: list, frame_size: tuple) -> float:
    """Compute bounding box jitter (normalized by frame size).

    Args:
        face_data: List of face data dicts.
        frame_size: (width, height) of frames.

    Returns:
        Average normalized bbox movement between frames.
    """
    if len(face_data) < 2:
        return 0.0

    w, h = frame_size
    norm_factor = math.sqrt(w * w + h * h)

    movements = []
    prev_bbox = None

    for fd in face_data:
        if fd is None:
            prev_bbox = None
            continue

        bbox = fd["bbox"]
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


def compute_landmark_jitter(face_data: list) -> float:
    """Compute landmark jitter (normalized by inter-ocular distance).

    Args:
        face_data: List of face data dicts.

    Returns:
        Average normalized landmark movement.
    """
    if len(face_data) < 2:
        return 0.0

    movements = []
    prev_landmarks = None
    prev_iod = None

    for fd in face_data:
        if fd is None or len(fd.get("landmarks", [])) == 0:
            prev_landmarks = None
            prev_iod = None
            continue

        landmarks = fd["landmarks"]

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


def compute_mouth_open_energy(face_data: list) -> float:
    """Compute variance of mouth openness over time.

    Args:
        face_data: List of face data dicts.

    Returns:
        Variance of mouth openness (higher = more movement).
    """
    openness_values = []
    for fd in face_data:
        if fd is not None and "mouth_openness" in fd:
            openness_values.append(fd["mouth_openness"])

    if len(openness_values) < 2:
        return 0.0

    mean_val = sum(openness_values) / len(openness_values)
    variance = sum((v - mean_val) ** 2 for v in openness_values) / len(openness_values)

    return variance


def compute_mouth_audio_corr(face_data: list, audio_envelope: object) -> float:
    """Compute correlation between mouth openness and audio envelope.

    Args:
        face_data: List of face data dicts.
        audio_envelope: Audio RMS envelope per frame.

    Returns:
        Correlation coefficient in [-1, 1], or 0 if cannot compute.
    """
    try:
        import numpy as np
    except ImportError:
        return 0.0

    if len(face_data) == 0 or len(audio_envelope) == 0:
        return 0.0

    # Extract mouth openness values
    mouth_values = []
    for fd in face_data:
        if fd is not None and "mouth_openness" in fd:
            mouth_values.append(fd["mouth_openness"])
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


def compute_blink_metrics(face_data: list, fps: float) -> tuple[int, float]:
    """Detect blinks using eye aspect ratio.

    Args:
        face_data: List of face data dicts.
        fps: Frames per second.

    Returns:
        Tuple of (blink_count, blink_rate_hz).
    """
    if len(face_data) == 0 or fps <= 0:
        return 0, 0.0

    # Extract EAR values
    ear_values = []
    for fd in face_data:
        if fd is not None and "eye_aspect_ratio" in fd:
            ear_values.append(fd["eye_aspect_ratio"])
        else:
            ear_values.append(0.3)  # Default open

    # Detect blinks (EAR below threshold for consecutive frames)
    blink_count = 0
    blink_frames = 0

    for ear in ear_values:
        if ear < EAR_THRESHOLD:
            blink_frames += 1
        else:
            if blink_frames >= BLINK_CONSEC_FRAMES:
                blink_count += 1
            blink_frames = 0

    # Check for blink at end
    if blink_frames >= BLINK_CONSEC_FRAMES:
        blink_count += 1

    # Compute rate
    duration_sec = len(face_data) / fps
    if duration_sec > 0:
        blink_rate = blink_count / duration_sec
    else:
        blink_rate = 0.0

    return blink_count, blink_rate


def compute_face_metrics(
    frames: list,
    audio_envelope: object,
    fps: float,
) -> dict:
    """Compute all face metrics.

    Args:
        frames: List of numpy array frames (BGR).
        audio_envelope: Audio RMS envelope per frame.
        fps: Frames per second.

    Returns:
        Dict with all Tier 1 metric fields.
    """
    # Extract face data
    face_data = extract_face_data(frames)

    # Compute metrics
    face_present_ratio = compute_face_present_ratio(face_data)

    # Get frame size for bbox jitter normalization
    if len(frames) > 0:
        h, w = frames[0].shape[:2]
        frame_size = (w, h)
    else:
        frame_size = (320, 240)

    face_bbox_jitter = compute_face_bbox_jitter(face_data, frame_size)
    landmark_jitter = compute_landmark_jitter(face_data)
    mouth_open_energy = compute_mouth_open_energy(face_data)
    mouth_audio_corr = compute_mouth_audio_corr(face_data, audio_envelope)
    blink_count, blink_rate_hz = compute_blink_metrics(face_data, fps)

    return {
        "face_present_ratio": face_present_ratio,
        "face_bbox_jitter": face_bbox_jitter,
        "landmark_jitter": landmark_jitter,
        "mouth_open_energy": mouth_open_energy,
        "mouth_audio_corr": mouth_audio_corr,
        "blink_count": blink_count,
        "blink_rate_hz": blink_rate_hz,
    }
