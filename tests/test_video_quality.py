"""Tests for video quality metrics.

Video quality metrics from METRICS.md:
- decode_ok: video can be decoded
- video_duration_ms, audio_duration_ms, av_duration_delta_ms
- fps, frame_count
- scene_cut_count
- freeze_frame_ratio
- flicker_score
- blur_score
- frame_diff_spike_count

Tests are organized into:
- Adapter tests: probe and decode via adapter/media
- Pure computation tests: metrics on numpy arrays
- Integration tests: full pipeline via bundle
"""

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from mirage.metrics.video_quality import (
    VideoQualityMetrics,
    compute_blur_score,
    compute_flicker_score,
    compute_frame_diff_spikes,
    compute_freeze_frame_ratio,
    compute_scene_cuts,
    compute_video_quality,
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


class TestProbeAdapter:
    """Tests for A/V probing via adapter."""

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_probe_video_returns_info(self):
        """Should return video metadata."""
        from mirage.adapter.media import probe_video

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
            video_path = Path(vf.name)

        try:
            create_test_video(video_path, duration=2.0, fps=30)

            info = probe_video(video_path)

            assert info.duration_ms > 0
            assert info.fps > 0
            assert info.frame_count > 0
            assert 1800 <= info.duration_ms <= 2200  # ~2 seconds
        finally:
            video_path.unlink(missing_ok=True)

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_probe_audio_returns_info(self):
        """Should return audio metadata."""
        from mirage.adapter.media import probe_audio

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af:
            audio_path = Path(af.name)

        try:
            create_test_audio(audio_path, duration=2.0)

            info = probe_audio(audio_path)

            assert info.duration_ms > 0
            assert 1800 <= info.duration_ms <= 2200
        finally:
            audio_path.unlink(missing_ok=True)

    def test_probe_raises_on_missing_file(self):
        """Should raise FileNotFoundError for missing file."""
        from mirage.adapter.media import probe_video

        with pytest.raises(FileNotFoundError):
            probe_video(Path("/nonexistent/video.mp4"))


class TestVideoReaderAdapter:
    """Tests for video decoding via adapter."""

    @pytest.mark.skipif(
        not (ffmpeg_available() and opencv_available()),
        reason="ffmpeg or opencv not available",
    )
    def test_decode_returns_frames(self):
        """Should return list of Frame objects."""
        from mirage.adapter.media.video_decode import VideoReader

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
            video_path = Path(vf.name)

        try:
            create_test_video(video_path, duration=0.5, fps=10)

            with VideoReader(video_path) as reader:
                frames = list(reader.iter_frames())

            assert len(frames) >= 4  # ~5 frames at 10fps for 0.5s
            assert hasattr(frames[0], "bgr")
            assert hasattr(frames[0], "index")
            assert hasattr(frames[0], "timestamp_ms")
        finally:
            video_path.unlink(missing_ok=True)

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_decode_nonexistent_raises(self):
        """Should raise for nonexistent video."""
        from mirage.adapter.media.video_decode import VideoReader

        with pytest.raises(FileNotFoundError):
            with VideoReader(Path("/nonexistent/video.mp4")) as reader:
                list(reader.iter_frames())


class TestComputeFreezeFrameRatio:
    """Tests for freeze frame detection - pure computation."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_ratio_between_0_and_1(self):
        """Should return ratio in [0, 1]."""
        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        ratio = compute_freeze_frame_ratio(frames)

        assert isinstance(ratio, float)
        assert 0.0 <= ratio <= 1.0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_identical_frames_high_ratio(self):
        """Identical frames should have high freeze ratio."""
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frames = [frame.copy() for _ in range(10)]

        ratio = compute_freeze_frame_ratio(frames)

        assert ratio > 0.8

    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        ratio = compute_freeze_frame_ratio([])
        assert ratio == 0.0


class TestComputeFlickerScore:
    """Tests for flicker detection - pure computation."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_non_negative_float(self):
        """Should return non-negative float."""
        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        score = compute_flicker_score(frames)

        assert isinstance(score, float)
        assert score >= 0.0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_stable_frames_low_flicker(self):
        """Stable luminance should have low flicker."""
        frame = np.full((240, 320, 3), 128, dtype=np.uint8)
        frames = [frame.copy() for _ in range(10)]

        score = compute_flicker_score(frames)

        assert score < 1.0

    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        score = compute_flicker_score([])
        assert score == 0.0


class TestComputeBlurScore:
    """Tests for blur detection - pure computation."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_non_negative_float(self):
        """Should return non-negative float."""
        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        score = compute_blur_score(frames)

        assert isinstance(score, float)
        assert score >= 0.0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_sharp_frames_high_score(self):
        """Sharp edges should have high blur score."""
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[100:140, 100:220] = 255
        frames = [frame.copy() for _ in range(5)]

        score = compute_blur_score(frames)

        assert score > 10.0

    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        score = compute_blur_score([])
        assert score == 0.0


class TestComputeSceneCuts:
    """Tests for scene cut detection - pure computation."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_non_negative_int(self):
        """Should return non-negative integer."""
        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        count = compute_scene_cuts(frames)

        assert isinstance(count, int)
        assert count >= 0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_abrupt_change_detected(self):
        """Abrupt scene change should be detected."""
        black = np.zeros((240, 320, 3), dtype=np.uint8)
        white = np.full((240, 320, 3), 255, dtype=np.uint8)
        frames = [black.copy() for _ in range(5)] + [white.copy() for _ in range(5)]

        count = compute_scene_cuts(frames)

        assert count >= 1

    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        count = compute_scene_cuts([])
        assert count == 0


class TestComputeFrameDiffSpikes:
    """Tests for frame difference spike detection - pure computation."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_non_negative_int(self):
        """Should return non-negative integer."""
        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        count = compute_frame_diff_spikes(frames)

        assert isinstance(count, int)
        assert count >= 0

    def test_empty_frames_returns_zero(self):
        """Empty frame list should return 0."""
        count = compute_frame_diff_spikes([])
        assert count == 0


class TestComputeVideoQuality:
    """Tests for the main compute_video_quality function."""

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_returns_typed_metrics(self):
        """Should return VideoQualityMetrics dataclass."""
        frames = [np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8) for _ in range(10)]

        metrics = compute_video_quality(
            frames=frames,
            video_duration_ms=1000,
            audio_duration_ms=1000,
            fps=30.0,
        )

        assert isinstance(metrics, VideoQualityMetrics)
        assert metrics.decode_ok is True
        assert metrics.frame_count == 10
        assert metrics.video_duration_ms == 1000
        assert metrics.fps == 30.0

    def test_empty_frames_returns_decode_false(self):
        """Empty frames should set decode_ok=False."""
        metrics = compute_video_quality(
            frames=[],
            video_duration_ms=1000,
            audio_duration_ms=1000,
            fps=30.0,
        )

        assert isinstance(metrics, VideoQualityMetrics)
        assert metrics.decode_ok is False
        assert metrics.frame_count == 0

    @pytest.mark.skipif(not opencv_available(), reason="opencv not available")
    def test_computes_av_delta(self):
        """Should compute A/V duration delta."""
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(10)]

        metrics = compute_video_quality(
            frames=frames,
            video_duration_ms=1000,
            audio_duration_ms=1200,
            fps=30.0,
        )

        assert metrics.av_duration_delta_ms == 200


class TestIntegrationWithBundle:
    """Integration tests using the bundle orchestrator."""

    @pytest.mark.skipif(
        not (ffmpeg_available() and opencv_available()),
        reason="ffmpeg or opencv not available",
    )
    def test_bundle_compute_metrics(self):
        """Should compute full MetricBundleV1."""
        from mirage.metrics.bundle import compute_metrics

        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
        ):
            video_path = Path(vf.name)
            audio_path = Path(af.name)

        try:
            create_test_video(video_path, duration=1.0, fps=30)
            create_test_audio(audio_path, duration=1.0)

            bundle = compute_metrics(video_path, audio_path)

            # Check typed result
            assert bundle.decode_ok is True
            assert bundle.video_duration_ms > 0
            assert bundle.fps > 0
            assert bundle.frame_count > 0
            assert 0.0 <= bundle.freeze_frame_ratio <= 1.0
            assert bundle.status_badge in ["pass", "flagged", "reject"]
        finally:
            video_path.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)

    def test_bundle_handles_missing_video(self):
        """Should handle missing video gracefully."""
        from mirage.metrics.bundle import compute_metrics

        bundle = compute_metrics(
            Path("/nonexistent/video.mp4"),
            Path("/nonexistent/audio.wav"),
        )

        assert bundle.decode_ok is False
        assert bundle.status_badge == "reject"
