"""Tests for demo seeding and smoke test.

TDD: Tests written first per IMPLEMENTATION_PLAN.md.
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


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


class TestSeedDemoScript:
    """Test seed_demo.py script."""

    def test_script_exists(self):
        """seed_demo.py script exists."""
        script_path = PROJECT_ROOT / "scripts" / "seed_demo.py"
        assert script_path.exists(), f"Script not found: {script_path}"

    def test_script_runs_without_error(self):
        """seed_demo.py runs without error."""
        script_path = PROJECT_ROOT / "scripts" / "seed_demo.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"

    def test_creates_demo_database(self):
        """seed_demo.py creates demo database."""
        script_path = PROJECT_ROOT / "scripts" / "seed_demo.py"
        subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        # Check database was created
        db_path = PROJECT_ROOT / "demo.db"
        assert db_path.exists(), "Demo database not created"


class TestSmokeDemoScript:
    """Test smoke_demo.py script."""

    def test_script_exists(self):
        """smoke_demo.py script exists."""
        script_path = PROJECT_ROOT / "scripts" / "smoke_demo.py"
        assert script_path.exists(), f"Script not found: {script_path}"

    @pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")
    def test_smoke_test_passes_after_seed(self):
        """smoke_demo.py passes after seed_demo.py runs."""
        # First seed the demo
        seed_script = PROJECT_ROOT / "scripts" / "seed_demo.py"
        subprocess.run(
            [sys.executable, str(seed_script)],
            capture_output=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )

        # Then run smoke test
        smoke_script = PROJECT_ROOT / "scripts" / "smoke_demo.py"
        result = subprocess.run(
            [sys.executable, str(smoke_script)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"Smoke test failed: {result.stderr}"


class TestDemoAssets:
    """Test demo assets exist."""

    def test_demo_assets_directory_exists(self):
        """demo_assets directory exists."""
        assets_dir = PROJECT_ROOT / "demo_assets"
        assert assets_dir.exists(), "demo_assets directory not found"

    def test_demo_video_exists(self):
        """Demo video file exists."""
        video_path = PROJECT_ROOT / "demo_assets" / "demo_source.mp4"
        assert video_path.exists(), "Demo video not found"

    def test_demo_audio_exists(self):
        """Demo audio file exists."""
        audio_path = PROJECT_ROOT / "demo_assets" / "demo_audio.wav"
        assert audio_path.exists(), "Demo audio not found"


class TestMetricBundleV1Keys:
    """Test that demo produces valid MetricBundleV1."""

    def test_metric_bundle_has_all_required_keys(self):
        """MetricBundleV1 from demo has all required keys."""
        from mirage.models.types import MetricBundleV1

        # Get expected fields from model
        expected_fields = set(MetricBundleV1.model_fields.keys())

        # These are the required fields per METRICS.md
        required_fields = {
            # Video quality
            "decode_ok",
            "video_duration_ms",
            "audio_duration_ms",
            "av_duration_delta_ms",
            "fps",
            "frame_count",
            "scene_cut_count",
            "freeze_frame_ratio",
            "flicker_score",
            "blur_score",
            "frame_diff_spike_count",
            # Face metrics
            "face_present_ratio",
            "face_bbox_jitter",
            "landmark_jitter",
            "mouth_open_energy",
            "mouth_audio_corr",
            "blink_count",
            "blink_rate_hz",
            # SyncNet (optional)
            "lse_d",
            "lse_c",
            # Status
            "status_badge",
            "reasons",
        }

        assert required_fields == expected_fields, (
            f"MetricBundleV1 fields mismatch. "
            f"Missing: {required_fields - expected_fields}, "
            f"Extra: {expected_fields - required_fields}"
        )
