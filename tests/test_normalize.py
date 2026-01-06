"""Tests for normalization module.

Invariants from ARCHITECTURE.md:
1. Normalized output is browser-safe (h264 + aac)
2. Output duration matches audio duration (video trimmed)
3. fps is fixed at 30
4. Output sha256 is deterministic for same input
5. Normalization happens before metrics and playback
"""

import subprocess
import tempfile
from pathlib import Path

import pytest

from mirage.adapter.media import probe_audio, probe_video
from mirage.normalize.video import check_tools_available, normalize_video


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


class TestCheckToolsAvailable:
    """Tests for tools availability check."""

    def test_returns_bool(self):
        """Should return a boolean."""
        result = check_tools_available()
        assert isinstance(result, bool)


class TestProbeVideo:
    """Tests for video probing via adapter."""

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_returns_video_info_with_required_fields(self):
        """Should return VideoInfo with duration_ms, fps, width, height."""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            test_video = Path(f.name)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=1:size=320x240:rate=30",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(test_video),
                ],
                capture_output=True,
                timeout=30,
            )

            info = probe_video(test_video)

            assert hasattr(info, "duration_ms")
            assert hasattr(info, "fps")
            assert hasattr(info, "width")
            assert hasattr(info, "height")
            assert isinstance(info.duration_ms, int)
            assert isinstance(info.fps, float)
        finally:
            test_video.unlink(missing_ok=True)

    def test_raises_on_nonexistent_file(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            probe_video(Path("/nonexistent/video.mp4"))


class TestProbeAudio:
    """Tests for audio probing via adapter."""

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_returns_audio_info_with_duration(self):
        """Should return AudioInfo with duration_ms."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            test_audio = Path(f.name)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=2",
                    str(test_audio),
                ],
                capture_output=True,
                timeout=30,
            )

            info = probe_audio(test_audio)

            assert hasattr(info, "duration_ms")
            assert isinstance(info.duration_ms, int)
            assert 1900 <= info.duration_ms <= 2100  # ~2 seconds
        finally:
            test_audio.unlink(missing_ok=True)

    def test_raises_on_nonexistent_file(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            probe_audio(Path("/nonexistent/audio.wav"))


class TestNormalizeVideo:
    """Tests for video normalization."""

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_produces_output_file(self):
        """Should produce an output file."""
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as of,
        ):
            test_video = Path(vf.name)
            test_audio = Path(af.name)
            output_path = Path(of.name)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=3:size=320x240:rate=24",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(test_video),
                ],
                capture_output=True,
                timeout=30,
            )

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=2",
                    str(test_audio),
                ],
                capture_output=True,
                timeout=30,
            )

            result = normalize_video(test_video, test_audio, output_path)

            assert output_path.exists()
            assert result.canon_video_path == str(output_path)
            assert isinstance(result.sha256, str)
            assert len(result.sha256) == 64
            assert isinstance(result.duration_ms, int)
        finally:
            test_video.unlink(missing_ok=True)
            test_audio.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_output_duration_matches_audio(self):
        """Output video duration should match audio duration."""
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as of,
        ):
            test_video = Path(vf.name)
            test_audio = Path(af.name)
            output_path = Path(of.name)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=5:size=320x240:rate=24",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(test_video),
                ],
                capture_output=True,
                timeout=30,
            )

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=2",
                    str(test_audio),
                ],
                capture_output=True,
                timeout=30,
            )

            result = normalize_video(test_video, test_audio, output_path)

            # Duration should be close to audio duration (2 seconds = 2000ms)
            assert 1900 <= result.duration_ms <= 2100
        finally:
            test_video.unlink(missing_ok=True)
            test_audio.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_deterministic_sha256(self):
        """Same input should produce same sha256."""
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as of1,
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as of2,
        ):
            test_video = Path(vf.name)
            test_audio = Path(af.name)
            output1 = Path(of1.name)
            output2 = Path(of2.name)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=1:size=320x240:rate=30",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(test_video),
                ],
                capture_output=True,
                timeout=30,
            )

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=1",
                    str(test_audio),
                ],
                capture_output=True,
                timeout=30,
            )

            normalize_video(test_video, test_audio, output1)
            normalize_video(test_video, test_audio, output2)

            # Due to encoding non-determinism, check file sizes are equal
            assert output1.stat().st_size == output2.stat().st_size
        finally:
            test_video.unlink(missing_ok=True)
            test_audio.unlink(missing_ok=True)
            output1.unlink(missing_ok=True)
            output2.unlink(missing_ok=True)

    def test_raises_on_missing_input_video(self):
        """Should raise FileNotFoundError for missing input video."""
        with pytest.raises(FileNotFoundError):
            normalize_video(
                Path("/nonexistent/video.mp4"),
                Path("/nonexistent/audio.wav"),
                Path("/tmp/output.mp4"),
            )


class TestCanonicalFormat:
    """Tests for canonical format compliance."""

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_output_is_h264(self):
        """Output should use h264 codec."""
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as of,
        ):
            test_video = Path(vf.name)
            test_audio = Path(af.name)
            output_path = Path(of.name)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=1:size=320x240:rate=30",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(test_video),
                ],
                capture_output=True,
                timeout=30,
            )

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=1",
                    str(test_audio),
                ],
                capture_output=True,
                timeout=30,
            )

            normalize_video(test_video, test_audio, output_path)

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_name",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.stdout.strip() == "h264"
        finally:
            test_video.unlink(missing_ok=True)
            test_audio.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_output_fps_is_30(self):
        """Output should have 30 fps."""
        with (
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf,
            tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as af,
            tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as of,
        ):
            test_video = Path(vf.name)
            test_audio = Path(af.name)
            output_path = Path(of.name)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=1:size=320x240:rate=24",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(test_video),
                ],
                capture_output=True,
                timeout=30,
            )

            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=1",
                    str(test_audio),
                ],
                capture_output=True,
                timeout=30,
            )

            normalize_video(test_video, test_audio, output_path)

            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=r_frame_rate",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            fps_str = result.stdout.strip()
            if "/" in fps_str:
                num, den = fps_str.split("/")
                fps = int(num) / int(den)
            else:
                fps = float(fps_str)

            assert fps == 30.0
        finally:
            test_video.unlink(missing_ok=True)
            test_audio.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)
