"""Face detection and landmark extraction via MediaPipe.

Adapter for MediaPipe Face Mesh model. Handles:
- Model initialization (stateful, reusable)
- Frame-by-frame face detection
- Landmark normalization
- Graceful fallback when mediapipe unavailable
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from mirage.adapter.media.video_decode import Frame


@dataclass
class FaceData:
    """Face detection result for a single frame.

    Attributes:
        detected: Whether a face was detected.
        bbox: Bounding box [x_min, y_min, x_max, y_max] in pixels.
        landmarks: List of [x, y] normalized coordinates (0-1).
        confidence: Detection confidence (0-1).
    """

    detected: bool = False
    bbox: list[float] = field(default_factory=list)
    landmarks: list[list[float]] = field(default_factory=list)
    confidence: float = 0.0


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


class FaceExtractor:
    """Stateful face detector using MediaPipe Face Mesh.

    Maintains model state to avoid re-initialization overhead.
    Thread-safe for single-threaded use (mediapipe limitation).

    Usage:
        extractor = FaceExtractor()
        track = extractor.extract_from_frames(frames)
        # or
        track = extractor.extract_from_video(video_path)
    """

    # MediaPipe face mesh landmark indices
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
        self._face_mesh = None
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

            if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "face_mesh"):
                self._available = False
                return False

            mp_face_mesh = mp.solutions.face_mesh
            self._face_mesh = mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=self._min_detection_conf,
                min_tracking_confidence=self._min_tracking_conf,
            )
            self._available = True
            return True

        except (ImportError, AttributeError):
            self._available = False
            return False

    def close(self) -> None:
        """Release mediapipe resources."""
        if self._face_mesh is not None:
            self._face_mesh.close()
            self._face_mesh = None
            self._available = None

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

        try:
            import cv2
        except ImportError:
            # cv2 needed for color conversion
            for frame in frames:
                track.frame_indices.append(frame.index)
                track.timestamps_ms.append(frame.timestamp_ms)
                track.face_data.append(FaceData(detected=False))
            return track

        for frame in frames:
            track.frame_indices.append(frame.index)
            track.timestamps_ms.append(frame.timestamp_ms)

            # Convert BGR to RGB for mediapipe
            rgb_frame = cv2.cvtColor(frame.bgr, cv2.COLOR_BGR2RGB)
            result = self._face_mesh.process(rgb_frame)

            if result.multi_face_landmarks and len(result.multi_face_landmarks) > 0:
                landmarks_raw = result.multi_face_landmarks[0].landmark
                h, w = frame.bgr.shape[:2]

                # Extract normalized landmarks
                landmarks = [[lm.x, lm.y] for lm in landmarks_raw]

                # Compute bounding box in pixels
                xs = [lm.x * w for lm in landmarks_raw]
                ys = [lm.y * h for lm in landmarks_raw]
                bbox = [min(xs), min(ys), max(xs), max(ys)]

                # Confidence from visibility scores
                confidence = np.mean([lm.visibility for lm in landmarks_raw])

                track.face_data.append(
                    FaceData(
                        detected=True,
                        bbox=bbox,
                        landmarks=landmarks,
                        confidence=float(confidence),
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
    """Check if mediapipe face mesh is available.

    Returns:
        True if mediapipe can be imported and has face_mesh.
    """
    try:
        import mediapipe as mp

        return hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh")
    except ImportError:
        return False
