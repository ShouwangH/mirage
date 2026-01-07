"""Face detection and landmark extraction via MediaPipe.

Adapter for MediaPipe Face Landmarker (tasks API). Handles:
- Model initialization (stateful, reusable)
- Frame-by-frame face detection
- Landmark normalization
- Blendshape extraction for mouth/eye tracking
- Graceful fallback when mediapipe unavailable
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from mirage.adapter.media.video_decode import Frame

# Model download URL and local path
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
MODEL_DIR = Path(__file__).parent.parent.parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "face_landmarker.task"


@dataclass
class FaceData:
    """Face detection result for a single frame.

    Attributes:
        detected: Whether a face was detected.
        bbox: Bounding box [x_min, y_min, x_max, y_max] in pixels.
        landmarks: List of [x, y] normalized coordinates (0-1).
        confidence: Detection confidence (0-1).
        mouth_open: Mouth openness from blendshapes (0-1).
        left_eye_open: Left eye openness from blendshapes (0-1).
        right_eye_open: Right eye openness from blendshapes (0-1).
    """

    detected: bool = False
    bbox: list[float] = field(default_factory=list)
    landmarks: list[list[float]] = field(default_factory=list)
    confidence: float = 0.0
    mouth_open: float = 0.0
    left_eye_open: float = 1.0
    right_eye_open: float = 1.0


@dataclass
class FaceTrack:
    """Face tracking results across multiple frames.

    Attributes:
        frame_indices: List of frame indices.
        timestamps_ms: List of timestamps in milliseconds.
        face_data: List of FaceData, one per frame.
        fps: Video frame rate used for timing.
    """

    frame_indices: list[int] = field(default_factory=list)
    timestamps_ms: list[int] = field(default_factory=list)
    face_data: list[FaceData] = field(default_factory=list)
    fps: float = 30.0

    @property
    def face_present_mask(self) -> list[bool]:
        """Boolean mask of frames with detected faces."""
        return [fd.detected for fd in self.face_data]

    @property
    def frame_count(self) -> int:
        """Number of frames processed."""
        return len(self.face_data)


def _ensure_model_downloaded() -> Path:
    """Download the face landmarker model if not present.

    Returns:
        Path to the model file.
    """
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if not MODEL_PATH.exists():
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

    return MODEL_PATH


class FaceExtractor:
    """Stateful face detector using MediaPipe Face Landmarker.

    Maintains model state to avoid re-initialization overhead.
    Uses the new mediapipe tasks API (0.10+).

    Usage:
        extractor = FaceExtractor()
        track = extractor.extract_from_frames(frames)
        # or
        track = extractor.extract_from_video(video_path)
    """

    # MediaPipe face mesh landmark indices (478 landmarks total)
    UPPER_LIP_IDX = 13
    LOWER_LIP_IDX = 14
    LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
    LEFT_EYE_CENTER = 33
    RIGHT_EYE_CENTER = 263

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ):
        """Initialize face extractor.

        Args:
            min_detection_confidence: Minimum detection confidence.
            min_tracking_confidence: Minimum tracking confidence.
        """
        self._min_detection_conf = min_detection_confidence
        self._min_tracking_conf = min_tracking_confidence
        self._landmarker = None
        self._available: bool | None = None

    def _ensure_initialized(self) -> bool:
        """Lazy initialization of mediapipe.

        Returns:
            True if mediapipe is available and initialized.
        """
        if self._available is not None:
            return self._available

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            # Ensure model is downloaded
            model_path = _ensure_model_downloaded()

            base_options = python.BaseOptions(model_asset_path=str(model_path))
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=self._min_detection_conf,
                min_face_presence_confidence=self._min_detection_conf,
                min_tracking_confidence=self._min_tracking_conf,
                output_face_blendshapes=True,
            )
            self._landmarker = vision.FaceLandmarker.create_from_options(options)
            self._mp = mp  # Store reference for Image creation
            self._available = True
            return True

        except (ImportError, AttributeError, Exception) as e:
            # Log error for debugging but don't crash
            import sys

            print(f"MediaPipe initialization failed: {e}", file=sys.stderr)
            self._available = False
            return False

    def close(self) -> None:
        """Release mediapipe resources."""
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
            self._available = None

    def _extract_blendshape_values(self, blendshapes: list) -> tuple[float, float, float]:
        """Extract mouth and eye openness from blendshapes.

        Args:
            blendshapes: List of blendshape categories from mediapipe.

        Returns:
            Tuple of (mouth_open, left_eye_open, right_eye_open).
        """
        mouth_open = 0.0
        left_eye_open = 1.0
        right_eye_open = 1.0

        for bs in blendshapes:
            name = bs.category_name.lower()
            if name == "jawopen":
                mouth_open = bs.score
            elif name == "eyelookinleft" or name == "eyeblinkleft":
                if name == "eyeblinkleft":
                    left_eye_open = 1.0 - bs.score
            elif name == "eyelookinright" or name == "eyeblinkright":
                if name == "eyeblinkright":
                    right_eye_open = 1.0 - bs.score

        return mouth_open, left_eye_open, right_eye_open

    def extract_from_frames(
        self,
        frames: list["Frame"],
        fps: float = 30.0,
    ) -> FaceTrack:
        """Extract face data from a list of frames.

        Args:
            frames: List of Frame objects from VideoReader.
            fps: Video frame rate for timing calculations.

        Returns:
            FaceTrack with detection results for each frame.
        """
        track = FaceTrack(fps=fps)

        if not self._ensure_initialized():
            # Return empty track with no-detection placeholders
            for frame in frames:
                track.frame_indices.append(frame.index)
                track.timestamps_ms.append(frame.timestamp_ms)
                track.face_data.append(FaceData(detected=False))
            return track

        for frame in frames:
            track.frame_indices.append(frame.index)
            track.timestamps_ms.append(frame.timestamp_ms)

            # Convert BGR to RGB and create mediapipe Image
            rgb_frame = frame.bgr[:, :, ::-1].copy()  # BGR to RGB
            mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb_frame)

            result = self._landmarker.detect(mp_image)

            if result.face_landmarks and len(result.face_landmarks) > 0:
                landmarks_raw = result.face_landmarks[0]
                h, w = frame.bgr.shape[:2]

                # Extract normalized landmarks
                landmarks = [[lm.x, lm.y] for lm in landmarks_raw]

                # Compute bounding box in pixels
                xs = [lm.x * w for lm in landmarks_raw]
                ys = [lm.y * h for lm in landmarks_raw]
                bbox = [min(xs), min(ys), max(xs), max(ys)]

                # Extract blendshape values for mouth/eye tracking
                mouth_open = 0.0
                left_eye_open = 1.0
                right_eye_open = 1.0

                if result.face_blendshapes and len(result.face_blendshapes) > 0:
                    mouth_open, left_eye_open, right_eye_open = self._extract_blendshape_values(
                        result.face_blendshapes[0]
                    )

                track.face_data.append(
                    FaceData(
                        detected=True,
                        bbox=bbox,
                        landmarks=landmarks,
                        confidence=1.0,  # New API doesn't expose per-landmark confidence
                        mouth_open=mouth_open,
                        left_eye_open=left_eye_open,
                        right_eye_open=right_eye_open,
                    )
                )
            else:
                track.face_data.append(FaceData(detected=False))

        return track

    def extract_from_bgr_arrays(
        self,
        bgr_arrays: list[np.ndarray],
        fps: float = 30.0,
    ) -> FaceTrack:
        """Extract face data from raw BGR numpy arrays.

        Convenience method for legacy code that doesn't use Frame objects.

        Args:
            bgr_arrays: List of BGR numpy arrays.
            fps: Video frame rate.

        Returns:
            FaceTrack with detection results.
        """
        from mirage.adapter.media.video_decode import Frame

        frames = [
            Frame(
                index=i,
                timestamp_ms=int(i / fps * 1000) if fps > 0 else 0,
                bgr=bgr,
            )
            for i, bgr in enumerate(bgr_arrays)
        ]
        return self.extract_from_frames(frames, fps=fps)


def check_available() -> bool:
    """Check if mediapipe face landmarker is available.

    Returns:
        True if mediapipe tasks API can be imported.
    """
    try:
        from mediapipe.tasks.python import vision

        return hasattr(vision, "FaceLandmarker")
    except ImportError:
        return False
