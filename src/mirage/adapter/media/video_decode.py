"""Video frame decoding via OpenCV.

Adapter for reading video frames from files. Handles:
- File open/close and resource cleanup
- Frame iteration with timestamps
- Optional downsampling for performance
- Graceful failure modes
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np


@dataclass
class Frame:
    """A single video frame with metadata."""

    index: int
    timestamp_ms: int
    bgr: np.ndarray  # BGR format as OpenCV provides


class VideoReader:
    """Video file reader with frame iteration.

    Provides a clean interface for reading video frames without
    exposing OpenCV internals to calling code.

    Usage:
        with VideoReader(path) as reader:
            for frame in reader.iter_frames(max_frames=100):
                process(frame.bgr)
    """

    def __init__(self, video_path: Path):
        """Initialize video reader.

        Args:
            video_path: Path to video file.

        Raises:
            FileNotFoundError: If video file doesn't exist.
        """
        self._path = Path(video_path)
        if not self._path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        self._cap = None
        self._fps: float = 30.0
        self._frame_count: int = 0
        self._width: int = 0
        self._height: int = 0

    def __enter__(self) -> "VideoReader":
        """Open video file."""
        self._open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close video file and release resources."""
        self._close()

    def _open(self) -> None:
        """Open video capture."""
        try:
            import cv2
        except ImportError as e:
            raise RuntimeError("OpenCV (cv2) is required for video decoding") from e

        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open video: {self._path}")

        self._fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
        self._frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def _close(self) -> None:
        """Release video capture."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def fps(self) -> float:
        """Video frame rate."""
        return self._fps

    @property
    def frame_count(self) -> int:
        """Total frame count (may be estimate)."""
        return self._frame_count

    @property
    def width(self) -> int:
        """Video width in pixels."""
        return self._width

    @property
    def height(self) -> int:
        """Video height in pixels."""
        return self._height

    @property
    def duration_ms(self) -> int:
        """Estimated duration in milliseconds."""
        if self._fps > 0:
            return int(self._frame_count / self._fps * 1000)
        return 0

    def iter_frames(
        self,
        max_frames: int | None = None,
        sample_every: int = 1,
        resize_width: int | None = None,
    ) -> Iterator[Frame]:
        """Iterate over video frames.

        Args:
            max_frames: Maximum frames to return (None = all).
            sample_every: Return every Nth frame (1 = all, 2 = half, etc).
            resize_width: Resize frames to this width (maintains aspect ratio).

        Yields:
            Frame objects with index, timestamp, and BGR data.

        Note:
            Must be called within context manager (with statement).
        """
        if self._cap is None:
            raise RuntimeError("VideoReader must be used as context manager")

        try:
            import cv2
        except ImportError:
            return

        frame_idx = 0
        yielded_count = 0

        while True:
            ret, bgr = self._cap.read()
            if not ret:
                break

            # Sample every Nth frame
            if frame_idx % sample_every == 0:
                # Compute timestamp
                timestamp_ms = int(frame_idx / self._fps * 1000) if self._fps > 0 else 0

                # Optional resize
                if resize_width is not None and bgr.shape[1] != resize_width:
                    scale = resize_width / bgr.shape[1]
                    new_height = int(bgr.shape[0] * scale)
                    bgr = cv2.resize(bgr, (resize_width, new_height))

                yield Frame(
                    index=frame_idx,
                    timestamp_ms=timestamp_ms,
                    bgr=bgr,
                )

                yielded_count += 1
                if max_frames is not None and yielded_count >= max_frames:
                    break

            frame_idx += 1


def decode_frames(
    video_path: Path,
    max_frames: int | None = None,
    sample_every: int = 1,
    resize_width: int | None = None,
) -> list[Frame]:
    """Convenience function to decode all frames to a list.

    For most use cases, prefer VideoReader.iter_frames() to avoid
    loading all frames into memory.

    Args:
        video_path: Path to video file.
        max_frames: Maximum frames to return.
        sample_every: Return every Nth frame.
        resize_width: Resize frames to this width.

    Returns:
        List of Frame objects.

    Raises:
        FileNotFoundError: If video file doesn't exist.
        RuntimeError: If video cannot be opened.
    """
    with VideoReader(video_path) as reader:
        return list(
            reader.iter_frames(
                max_frames=max_frames,
                sample_every=sample_every,
                resize_width=resize_width,
            )
        )
