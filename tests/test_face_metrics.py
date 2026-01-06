"""Tests for face metrics - pure computation functions.

Face metrics from METRICS.md:
- face_present_ratio: % frames with detected face
- face_bbox_jitter: bbox stability
- landmark_jitter: landmark stability
- mouth_open_energy: mouth movement variance
- mouth_audio_corr: mouth-audio correlation
- blink_count, blink_rate_hz: blink detection

Tests are organized into:
- Adapter tests: face extraction via adapter/vision
- Pure computation tests: metrics on FaceTrack domain objects
- Integration tests: full pipeline via bundle
"""

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from mirage.adapter.vision.mediapipe_face import FaceData, FaceTrack
from mirage.metrics.face_metrics import FaceMetrics, compute_face_metrics


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


def make_face_track(
    face_data_list: list[FaceData | None],
    fps: float = 30.0,
) -> FaceTrack:
    """Helper to create FaceTrack from list of FaceData."""
    track = FaceTrack(fps=fps)
    for i, fd in enumerate(face_data_list):
        track.frame_indices.append(i)
        track.timestamps_ms.append(int(i / fps * 1000))
        if fd is not None:
            track.face_data.append(fd)
        else:
            track.face_data.append(FaceData(detected=False))
    return track


class TestFaceExtractorAdapter:
    """Tests for face extraction via adapter."""

    @pytest.mark.skipif(
        not (opencv_available() and mediapipe_available()),
        reason="opencv or mediapipe not available",
    )
    def test_returns_face_track(self):
        """Should return FaceTrack with detection results."""
        from mirage.adapter.vision.mediapipe_face import FaceExtractor

        extractor = FaceExtractor()
        bgr_arrays = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(5)]
        track = extractor.extract_from_bgr_arrays(bgr_arrays)

        assert isinstance(track, FaceTrack)
        assert track.frame_count == len(bgr_arrays)
        for fd in track.face_data:
            assert isinstance(fd, FaceData)
            assert hasattr(fd, "detected")

    def test_empty_frames_returns_empty_track(self):
        """Empty frame list should return empty track."""
        from mirage.adapter.vision.mediapipe_face import FaceExtractor

        extractor = FaceExtractor()
        track = extractor.extract_from_bgr_arrays([])

        assert isinstance(track, FaceTrack)
        assert track.frame_count == 0


class TestComputeFaceMetrics:
    """Tests for compute_face_metrics with typed FaceTrack."""

    def test_returns_face_metrics_type(self):
        """Should return FaceMetrics dataclass."""
        track = FaceTrack(fps=30.0)
        metrics = compute_face_metrics(track, (320, 240), [])

        assert isinstance(metrics, FaceMetrics)

    def test_empty_track_returns_defaults(self):
        """Empty FaceTrack should return default values."""
        track = FaceTrack(fps=30.0)
        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.face_present_ratio == 0.0
        assert metrics.face_bbox_jitter == 0.0
        assert metrics.landmark_jitter == 0.0
        assert metrics.mouth_open_energy == 0.0
        assert metrics.mouth_audio_corr == 0.0
        assert metrics.blink_count is None
        assert metrics.blink_rate_hz is None

    def test_no_faces_detected_zero_ratio(self):
        """No faces detected should return ratio 0."""
        face_data = [
            FaceData(detected=False),
            FaceData(detected=False),
            FaceData(detected=False),
        ]
        track = make_face_track(face_data)

        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.face_present_ratio == 0.0

    def test_all_faces_detected_ratio_one(self):
        """All faces detected should return ratio 1."""
        face_data = [
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=[]),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=[]),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=[]),
        ]
        track = make_face_track(face_data)

        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.face_present_ratio == 1.0

    def test_partial_faces_correct_ratio(self):
        """Partial face detection should return correct ratio."""
        face_data = [
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=[]),
            FaceData(detected=False),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=[]),
            FaceData(detected=False),
        ]
        track = make_face_track(face_data)

        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.face_present_ratio == 0.5

    def test_stable_bbox_low_jitter(self):
        """Stable bounding boxes should have low jitter."""
        face_data = [
            FaceData(detected=True, bbox=[100, 100, 200, 200], landmarks=[]),
            FaceData(detected=True, bbox=[100, 100, 200, 200], landmarks=[]),
            FaceData(detected=True, bbox=[100, 100, 200, 200], landmarks=[]),
        ]
        track = make_face_track(face_data)

        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.face_bbox_jitter == 0.0

    def test_moving_bbox_has_jitter(self):
        """Moving bounding boxes should have positive jitter."""
        face_data = [
            FaceData(detected=True, bbox=[100, 100, 200, 200], landmarks=[]),
            FaceData(detected=True, bbox=[110, 110, 210, 210], landmarks=[]),
            FaceData(detected=True, bbox=[120, 120, 220, 220], landmarks=[]),
        ]
        track = make_face_track(face_data)

        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.face_bbox_jitter > 0.0

    def test_stable_landmarks_low_jitter(self):
        """Stable landmarks should have low jitter."""
        # Need enough landmarks for inter-ocular distance (indices 33, 263)
        landmarks = [[0.5, 0.5]] * 500
        landmarks[33] = [0.4, 0.5]  # Left eye
        landmarks[263] = [0.6, 0.5]  # Right eye

        face_data = [
            FaceData(detected=True, bbox=[100, 100, 200, 200], landmarks=landmarks.copy()),
            FaceData(detected=True, bbox=[100, 100, 200, 200], landmarks=landmarks.copy()),
            FaceData(detected=True, bbox=[100, 100, 200, 200], landmarks=landmarks.copy()),
        ]
        track = make_face_track(face_data)

        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.landmark_jitter == 0.0

    def test_blink_detection_returns_count_and_rate(self):
        """Should return blink count and rate."""
        # Create landmarks with enough points
        landmarks = [[0.5, 0.5]] * 500

        face_data = [
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
        ]
        track = make_face_track(face_data, fps=30.0)

        metrics = compute_face_metrics(track, (320, 240), [])

        assert isinstance(metrics.blink_count, int)
        assert metrics.blink_count >= 0
        assert isinstance(metrics.blink_rate_hz, float)
        assert metrics.blink_rate_hz >= 0.0


class TestMouthAudioCorrelation:
    """Tests for mouth-audio correlation computation."""

    def test_returns_value_in_range(self):
        """Correlation should be in [-1, 1]."""
        # Create landmarks with lip points
        landmarks = [[0.5, 0.5]] * 500
        landmarks[13] = [0.5, 0.4]  # Upper lip
        landmarks[14] = [0.5, 0.5]  # Lower lip

        face_data = [
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
        ]
        track = make_face_track(face_data)
        audio_envelope = [0.1, 0.4, 0.7, 0.2]

        metrics = compute_face_metrics(track, (320, 240), audio_envelope)

        assert -1.0 <= metrics.mouth_audio_corr <= 1.0

    def test_empty_data_returns_zero(self):
        """Empty data should return 0 correlation."""
        track = FaceTrack(fps=30.0)
        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.mouth_audio_corr == 0.0


class TestMouthOpenEnergy:
    """Tests for mouth open energy computation."""

    def test_stable_mouth_low_energy(self):
        """Stable mouth openness should have low energy."""
        landmarks = [[0.5, 0.5]] * 500
        landmarks[13] = [0.5, 0.4]  # Upper lip
        landmarks[14] = [0.5, 0.5]  # Lower lip - constant distance

        face_data = [
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=landmarks.copy()),
        ]
        track = make_face_track(face_data)

        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.mouth_open_energy == 0.0

    def test_varying_mouth_has_energy(self):
        """Varying mouth openness should have positive energy."""
        base_landmarks = [[0.5, 0.5]] * 500

        lm1 = base_landmarks.copy()
        lm1[13] = [0.5, 0.4]
        lm1[14] = [0.5, 0.42]  # Small opening

        lm2 = base_landmarks.copy()
        lm2[13] = [0.5, 0.4]
        lm2[14] = [0.5, 0.6]  # Large opening

        lm3 = base_landmarks.copy()
        lm3[13] = [0.5, 0.4]
        lm3[14] = [0.5, 0.45]  # Medium opening

        face_data = [
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=lm1),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=lm2),
            FaceData(detected=True, bbox=[0, 0, 100, 100], landmarks=lm3),
        ]
        track = make_face_track(face_data)

        metrics = compute_face_metrics(track, (320, 240), [])

        assert metrics.mouth_open_energy > 0.0


class TestIntegrationWithBundle:
    """Integration tests using the bundle orchestrator."""

    @pytest.mark.skipif(
        not (ffmpeg_available() and opencv_available() and mediapipe_available()),
        reason="ffmpeg, opencv, or mediapipe not available",
    )
    def test_bundle_includes_face_metrics(self):
        """Bundle should include face metrics."""
        from mirage.metrics.bundle import compute_metrics

        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
        ):
            video_path = Path(vf.name)
            audio_path = Path(af.name)

        try:
            create_test_video(video_path, duration=0.5, fps=10)
            create_test_audio(audio_path, duration=0.5)

            bundle = compute_metrics(video_path, audio_path)

            # Check face metric fields exist and have valid types
            assert isinstance(bundle.face_present_ratio, float)
            assert isinstance(bundle.face_bbox_jitter, float)
            assert isinstance(bundle.landmark_jitter, float)
            assert isinstance(bundle.mouth_open_energy, float)
            assert isinstance(bundle.mouth_audio_corr, float)
            assert 0.0 <= bundle.face_present_ratio <= 1.0
        finally:
            video_path.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)
