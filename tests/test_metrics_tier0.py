"""Tests for Tier 0 metrics (ffmpeg/opencv/numpy).

Tier 0 metrics from METRICS.md:
- decode_ok: video can be decoded
- video_duration_ms, audio_duration_ms, av_duration_delta_ms
- fps, frame_count
- scene_cut_count
- freeze_frame_ratio
- flicker_score
- blur_score
- frame_diff_spike_count
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

from mirage.metrics.tier0 import (
    compute_blur_score,
    compute_flicker_score,
    compute_frame_diff_spikes,
    compute_freeze_frame_ratio,
    compute_scene_cuts,
    compute_tier0_metrics,
    decode_video,
    get_av_info,
)


def ffmpeg_available() -> bool:
    """Check if ffmpeg is available for integration tests."""
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


class TestGetAvInfo:
    """Tests for A/V info extraction."""

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_returns_durations_and_fps(self):
        """Should return video duration, audio duration, fps, frame count."""
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
        ):
            video_path = Path(vf.name)
            audio_path = Path(af.name)

        try:
            create_test_video(video_path, duration=2.0, fps=30)
            create_test_audio(audio_path, duration=2.0)

            info = get_av_info(video_path, audio_path)

            assert "video_duration_ms" in info
            assert "audio_duration_ms" in info
            assert "av_duration_delta_ms" in info
            assert "fps" in info
            assert "frame_count" in info
            assert isinstance(info["video_duration_ms"], int)
            assert isinstance(info["fps"], float)
            # ~2 seconds
            assert 1800 <= info["video_duration_ms"] <= 2200
        finally:
            video_path.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)

    def test_raises_on_missing_video(self):
        """Should raise FileNotFoundError for missing video."""
        with pytest.raises(FileNotFoundError):
            get_av_info(Path("/nonexistent/video.mp4"), Path("/nonexistent/audio.wav"))


class TestDecodeVideo:
    """Tests for video decoding."""

    @pytest.mark.skipif(
        not (ffmpeg_available() and opencv_available()),
        reason="ffmpeg or opencv not available",
    )
    def test_decode_returns_frames(self):
        """Should return list of frames."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
            video_path = Path(vf.name)

        try:
            create_test_video(video_path, duration=0.5, fps=10)

            frames = decode_video(video_path)

            assert isinstance(frames, list)
            assert len(frames) >= 4  # ~5 frames at 10fps for 0.5s
            # Each frame should be a numpy array
            assert hasattr(frames[0], "shape")
        finally:
            video_path.unlink(missing_ok=True)

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_decode_nonexistent_returns_empty(self):
        """Should return empty list for nonexistent video."""
        frames = decode_video(Path("/nonexistent/video.mp4"))
        assert frames == []


class TestComputeFreezeFrameRatio:
    """Tests for freeze frame detection."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_ratio_between_0_and_1(self):
        """Should return ratio in [0, 1]."""
        import numpy as np

        # Create fake frames with slight differences
        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        ratio = compute_freeze_frame_ratio(frames)

        assert isinstance(ratio, float)
        assert 0.0 <= ratio <= 1.0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_identical_frames_high_ratio(self):
        """Identical frames should have high freeze ratio."""
        import numpy as np

        # All identical frames
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frames = [frame.copy() for _ in range(10)]

        ratio = compute_freeze_frame_ratio(frames)

        assert ratio > 0.8  # Most frames should be "frozen"

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        ratio = compute_freeze_frame_ratio([])
        assert ratio == 0.0


class TestComputeFlickerScore:
    """Tests for flicker detection."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_non_negative_float(self):
        """Should return non-negative float."""
        import numpy as np

        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        score = compute_flicker_score(frames)

        assert isinstance(score, float)
        assert score >= 0.0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_stable_frames_low_flicker(self):
        """Stable luminance should have low flicker."""
        import numpy as np

        # All same brightness
        frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        frames = [frame.copy() for _ in range(10)]

        score = compute_flicker_score(frames)

        assert score < 1.0  # Very low flicker

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        score = compute_flicker_score([])
        assert score == 0.0


class TestComputeBlurScore:
    """Tests for blur detection."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_non_negative_float(self):
        """Should return non-negative float."""
        import numpy as np

        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        score = compute_blur_score(frames)

        assert isinstance(score, float)
        assert score >= 0.0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_sharp_frames_high_score(self):
        """Sharp edges should have high blur score (variance of Laplacian)."""
        import numpy as np

        # Create frame with sharp edges
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[100:140, 100:220] = 255  # Sharp rectangle
        frames = [frame.copy() for _ in range(5)]

        score = compute_blur_score(frames)

        assert score > 10.0  # Sharp edges = high variance

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        score = compute_blur_score([])
        assert score == 0.0


class TestComputeSceneCuts:
    """Tests for scene cut detection."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_non_negative_int(self):
        """Should return non-negative integer."""
        import numpy as np

        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        count = compute_scene_cuts(frames)

        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_abrupt_change_detected(self):
        """Abrupt scene change should be detected."""
        import numpy as np

        # First 5 frames black, next 5 white
        black = np.zeros((240, 320, 3), dtype=np.uint8)
        white = np.full((240, 320, 3), 255, dtype=np.uint8)
        frames = [black.copy() for _ in range(5)] + [white.copy() for _ in range(5)]

        count = compute_scene_cuts(frames)

        assert count >= 1  # At least one scene cut

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        count = compute_scene_cuts([])
        assert count == 0


class TestComputeFrameDiffSpikes:
    """Tests for frame difference spike detection."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_non_negative_int(self):
        """Should return non-negative integer."""
        import numpy as np

        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        count = compute_frame_diff_spikes(frames)

        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        count = compute_frame_diff_spikes([])
        assert count == 0


class TestComputeTier0Metrics:
    """Integration tests for full Tier 0 metrics computation."""

    @pytest.mark.skipif(
        not (ffmpeg_available() and opencv_available()),
        reason="ffmpeg or opencv not available",
    )
    def test_returns_all_tier0_fields(self):
        """Should return dict with all Tier 0 metric fields."""
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
        ):
            video_path = Path(vf.name)
            audio_path = Path(af.name)

        try:
            create_test_video(video_path, duration=1.0, fps=30)
            create_test_audio(audio_path, duration=1.0)

            metrics = compute_tier0_metrics(video_path, audio_path)

            # Check all Tier 0 fields
            assert "decode_ok" in metrics
            assert "video_duration_ms" in metrics
            assert "audio_duration_ms" in metrics
            assert "av_duration_delta_ms" in metrics
            assert "fps" in metrics
            assert "frame_count" in metrics
            assert "scene_cut_count" in metrics
            assert "freeze_frame_ratio" in metrics
            assert "flicker_score" in metrics
            assert "blur_score" in metrics
            assert "frame_diff_spike_count" in metrics

            # Check types
            assert isinstance(metrics["decode_ok"], bool)
            assert isinstance(metrics["video_duration_ms"], int)
            assert isinstance(metrics["fps"], float)
            assert isinstance(metrics["freeze_frame_ratio"], float)
        finally:
            video_path.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)

    @pytest.mark.skipif(
        not (ffmpeg_available() and opencv_available()),
        reason="ffmpeg or opencv not available",
    )
    def test_decode_ok_true_for_valid_video(self):
        """decode_ok should be True for valid video."""
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
        ):
            video_path = Path(vf.name)
            audio_path = Path(af.name)

        try:
            create_test_video(video_path, duration=1.0, fps=30)
            create_test_audio(audio_path, duration=1.0)

            metrics = compute_tier0_metrics(video_path, audio_path)

            assert metrics["decode_ok"] is True
        finally:
            video_path.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)

    def test_decode_ok_false_for_invalid_video(self):
        """decode_ok should be False for invalid video."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af:
            audio_path = Path(af.name)

        try:
            create_test_audio(audio_path, duration=1.0) if ffmpeg_available() else None

            metrics = compute_tier0_metrics(
                Path("/nonexistent/video.mp4"),
                audio_path if audio_path.exists() else Path("/nonexistent/audio.wav"),
            )

            assert metrics["decode_ok"] is False
        finally:
            audio_path.unlink(missing_ok=True)
