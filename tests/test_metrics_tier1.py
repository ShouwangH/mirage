"""Tests for Tier 1 metrics (mediapipe).

Tier 1 metrics from METRICS.md:
- face_present_ratio: % frames with detected face
- face_bbox_jitter: bbox stability
- landmark_jitter: landmark stability
- mouth_open_energy: mouth movement variance
- mouth_audio_corr: mouth-audio correlation
- blink_count, blink_rate_hz: optional blink detection
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

from mirage.metrics.tier1 import (
    compute_blink_metrics,
    compute_face_bbox_jitter,
    compute_face_present_ratio,
    compute_landmark_jitter,
    compute_mouth_audio_corr,
    compute_mouth_open_energy,
    compute_tier1_metrics,
    extract_face_data,
)


def ffmpeg_available() -> bool:
    """Check if ffmpeg is available."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def mediapipe_available() -> bool:
    """Check if mediapipe is available and has expected API."""
    try:
        import mediapipe as mp

        return hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh")
    except (ImportError, AttributeError):
        return False


def opencv_available() -> bool:
    """Check if opencv is available."""
    import importlib.util

    return importlib.util.find_spec("cv2") is not None


def create_test_video(path: Path, duration: float = 1.0, fps: int = 30) -> None:
    """Create a test video using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration}:size=320x240:rate={fps}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        capture_output=True,
        timeout=30,
    )


def create_test_audio(path: Path, duration: float = 1.0) -> None:
    """Create a test audio using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            str(path),
        ],
        capture_output=True,
        timeout=30,
    )


class TestExtractFaceData:
    """Tests for face data extraction."""

    @pytest.mark.skipif(
        not (opencv_available() and mediapipe_available()),
        reason="opencv or mediapipe not available",
    )
    def test_returns_list_of_face_data(self):
        """Should return list of face data dicts per frame."""
        import numpy as np

        # Create simple test frames (no real face, but tests structure)
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(5)]

        face_data = extract_face_data(frames)

        assert isinstance(face_data, list)
        assert len(face_data) == len(frames)
        # Each entry should be dict or None
        for entry in face_data:
            assert entry is None or isinstance(entry, dict)

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_empty_frames_returns_empty(self):
        """Empty frame list should return empty list."""
        face_data = extract_face_data([])
        assert face_data == []


class TestComputeFacePresentRatio:
    """Tests for face presence ratio."""

    def test_no_faces_returns_zero(self):
        """No faces detected should return 0."""
        face_data = [None, None, None]
        ratio = compute_face_present_ratio(face_data)
        assert ratio == 0.0

    def test_all_faces_returns_one(self):
        """All faces detected should return 1."""
        face_data = [
            {"bbox": [0, 0, 100, 100], "landmarks": []},
            {"bbox": [0, 0, 100, 100], "landmarks": []},
            {"bbox": [0, 0, 100, 100], "landmarks": []},
        ]
        ratio = compute_face_present_ratio(face_data)
        assert ratio == 1.0

    def test_partial_faces(self):
        """Partial face detection should return correct ratio."""
        face_data = [
            {"bbox": [0, 0, 100, 100], "landmarks": []},
            None,
            {"bbox": [0, 0, 100, 100], "landmarks": []},
            None,
        ]
        ratio = compute_face_present_ratio(face_data)
        assert ratio == 0.5

    def test_empty_returns_zero(self):
        """Empty list should return 0."""
        ratio = compute_face_present_ratio([])
        assert ratio == 0.0


class TestComputeFaceBboxJitter:
    """Tests for face bounding box jitter."""

    def test_stable_bbox_low_jitter(self):
        """Stable bounding box should have low jitter."""
        face_data = [
            {"bbox": [100, 100, 200, 200], "landmarks": []},
            {"bbox": [100, 100, 200, 200], "landmarks": []},
            {"bbox": [100, 100, 200, 200], "landmarks": []},
        ]
        jitter = compute_face_bbox_jitter(face_data, frame_size=(320, 240))
        assert jitter == 0.0

    def test_moving_bbox_has_jitter(self):
        """Moving bounding box should have positive jitter."""
        face_data = [
            {"bbox": [100, 100, 200, 200], "landmarks": []},
            {"bbox": [110, 110, 210, 210], "landmarks": []},
            {"bbox": [120, 120, 220, 220], "landmarks": []},
        ]
        jitter = compute_face_bbox_jitter(face_data, frame_size=(320, 240))
        assert jitter > 0.0

    def test_empty_returns_zero(self):
        """Empty list should return 0."""
        jitter = compute_face_bbox_jitter([], frame_size=(320, 240))
        assert jitter == 0.0

    def test_single_frame_returns_zero(self):
        """Single frame should return 0 jitter."""
        face_data = [{"bbox": [100, 100, 200, 200], "landmarks": []}]
        jitter = compute_face_bbox_jitter(face_data, frame_size=(320, 240))
        assert jitter == 0.0


class TestComputeLandmarkJitter:
    """Tests for landmark jitter."""

    def test_stable_landmarks_low_jitter(self):
        """Stable landmarks should have low jitter."""
        landmarks = [[0.5, 0.5], [0.6, 0.5], [0.4, 0.5]]  # Simple 3 points
        face_data = [
            {"bbox": [100, 100, 200, 200], "landmarks": landmarks},
            {"bbox": [100, 100, 200, 200], "landmarks": landmarks},
            {"bbox": [100, 100, 200, 200], "landmarks": landmarks},
        ]
        jitter = compute_landmark_jitter(face_data)
        assert jitter == 0.0

    def test_moving_landmarks_has_jitter(self):
        """Moving landmarks should have positive jitter."""
        face_data = [
            {"bbox": [100, 100, 200, 200], "landmarks": [[0.5, 0.5], [0.6, 0.5]]},
            {"bbox": [100, 100, 200, 200], "landmarks": [[0.55, 0.55], [0.65, 0.55]]},
            {"bbox": [100, 100, 200, 200], "landmarks": [[0.6, 0.6], [0.7, 0.6]]},
        ]
        jitter = compute_landmark_jitter(face_data)
        assert jitter > 0.0

    def test_empty_returns_zero(self):
        """Empty list should return 0."""
        jitter = compute_landmark_jitter([])
        assert jitter == 0.0


class TestComputeMouthOpenEnergy:
    """Tests for mouth open energy."""

    def test_stable_mouth_low_energy(self):
        """Stable mouth openness should have low energy."""
        # All same mouth openness
        face_data = [
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.5},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.5},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.5},
        ]
        energy = compute_mouth_open_energy(face_data)
        assert energy == 0.0

    def test_varying_mouth_has_energy(self):
        """Varying mouth openness should have positive energy."""
        face_data = [
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.2},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.8},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.3},
        ]
        energy = compute_mouth_open_energy(face_data)
        assert energy > 0.0

    def test_empty_returns_zero(self):
        """Empty list should return 0."""
        energy = compute_mouth_open_energy([])
        assert energy == 0.0


class TestComputeMouthAudioCorr:
    """Tests for mouth-audio correlation."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_value_in_range(self):
        """Correlation should be in [-1, 1]."""
        import numpy as np

        face_data = [
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.2},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.5},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.8},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "mouth_openness": 0.3},
        ]
        # Fake audio envelope
        audio_envelope = np.array([0.1, 0.4, 0.7, 0.2])

        corr = compute_mouth_audio_corr(face_data, audio_envelope)

        assert -1.0 <= corr <= 1.0

    def test_empty_returns_zero(self):
        """Empty data should return 0."""
        import numpy as np

        corr = compute_mouth_audio_corr([], np.array([]))
        assert corr == 0.0


class TestComputeBlinkMetrics:
    """Tests for blink detection."""

    def test_returns_count_and_rate(self):
        """Should return blink count and rate."""
        # Simulate eye aspect ratios with blinks
        face_data = [
            {"bbox": [0, 0, 100, 100], "landmarks": [], "eye_aspect_ratio": 0.3},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "eye_aspect_ratio": 0.3},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "eye_aspect_ratio": 0.1},  # Blink
            {"bbox": [0, 0, 100, 100], "landmarks": [], "eye_aspect_ratio": 0.3},
            {"bbox": [0, 0, 100, 100], "landmarks": [], "eye_aspect_ratio": 0.3},
        ]
        count, rate = compute_blink_metrics(face_data, fps=30.0)

        assert isinstance(count, int)
        assert count >= 0
        assert isinstance(rate, float)
        assert rate >= 0.0

    def test_empty_returns_zero(self):
        """Empty data should return zeros."""
        count, rate = compute_blink_metrics([], fps=30.0)
        assert count == 0
        assert rate == 0.0


class TestComputeTier1Metrics:
    """Integration tests for full Tier 1 metrics."""

    @pytest.mark.skipif(
        not (opencv_available() and mediapipe_available()),
        reason="opencv or mediapipe not available",
    )
    def test_returns_all_tier1_fields(self):
        """Should return dict with all Tier 1 fields."""
        import numpy as np

        # Create simple test frames
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(5)]
        audio_envelope = np.array([0.1, 0.2, 0.3, 0.2, 0.1])

        metrics = compute_tier1_metrics(frames, audio_envelope, fps=30.0)

        # Check all Tier 1 fields
        assert "face_present_ratio" in metrics
        assert "face_bbox_jitter" in metrics
        assert "landmark_jitter" in metrics
        assert "mouth_open_energy" in metrics
        assert "mouth_audio_corr" in metrics
        assert "blink_count" in metrics
        assert "blink_rate_hz" in metrics

        # Check types
        assert isinstance(metrics["face_present_ratio"], float)
        assert isinstance(metrics["face_bbox_jitter"], float)
        assert 0.0 <= metrics["face_present_ratio"] <= 1.0

    def test_empty_frames_returns_defaults(self):
        """Empty frames should return default values."""
        import numpy as np

        metrics = compute_tier1_metrics([], np.array([]), fps=30.0)

        assert metrics["face_present_ratio"] == 0.0
        assert metrics["face_bbox_jitter"] == 0.0
        assert metrics["blink_count"] == 0


class TestIntegrationWithVideo:
    """Integration tests with actual video files."""

    @pytest.mark.skipif(
        not (ffmpeg_available() and opencv_available() and mediapipe_available()),
        reason="ffmpeg, opencv, or mediapipe not available",
    )
    def test_process_test_video(self):
        """Should process a test video without errors."""
        from mirage.metrics.tier0 import decode_video

        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
        ):
            video_path = Path(vf.name)
            audio_path = Path(af.name)

        try:
            create_test_video(video_path, duration=0.5, fps=10)
            create_test_audio(audio_path, duration=0.5)

            # Decode frames
            frames = decode_video(video_path)
            assert len(frames) > 0

            # Create fake audio envelope
            import numpy as np

            audio_envelope = np.random.rand(len(frames))

            # Compute metrics
            metrics = compute_tier1_metrics(frames, audio_envelope, fps=10.0)

            assert "face_present_ratio" in metrics
            assert "mouth_audio_corr" in metrics
        finally:
            video_path.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)
