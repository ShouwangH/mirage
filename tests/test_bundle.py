"""Tests for MetricBundleV1 assembly.

TDD: Tests written first per IMPLEMENTATION_PLAN.md.
"""

import pytest

from mirage.metrics.bundle import compute_metrics
from mirage.models.types import MetricBundleV1


class TestComputeMetricsSignature:
    """Test compute_metrics function signature and return type."""

    def test_returns_metric_bundle_v1(self, tmp_path):
        """compute_metrics returns MetricBundleV1 instance."""
        # Create dummy files (will fail decode but should return valid bundle)
        video_path = tmp_path / "test.mp4"
        audio_path = tmp_path / "test.wav"
        video_path.write_bytes(b"not a video")
        audio_path.write_bytes(b"not audio")

        result = compute_metrics(video_path, audio_path)

        assert isinstance(result, MetricBundleV1)

    def test_has_all_tier0_fields(self, tmp_path):
        """Result has all Tier 0 metric fields."""
        video_path = tmp_path / "test.mp4"
        audio_path = tmp_path / "test.wav"
        video_path.write_bytes(b"not a video")
        audio_path.write_bytes(b"not audio")

        result = compute_metrics(video_path, audio_path)

        # Tier 0 fields
        assert hasattr(result, "decode_ok")
        assert hasattr(result, "video_duration_ms")
        assert hasattr(result, "audio_duration_ms")
        assert hasattr(result, "av_duration_delta_ms")
        assert hasattr(result, "fps")
        assert hasattr(result, "frame_count")
        assert hasattr(result, "scene_cut_count")
        assert hasattr(result, "freeze_frame_ratio")
        assert hasattr(result, "flicker_score")
        assert hasattr(result, "blur_score")
        assert hasattr(result, "frame_diff_spike_count")

    def test_has_all_tier1_fields(self, tmp_path):
        """Result has all Tier 1 metric fields."""
        video_path = tmp_path / "test.mp4"
        audio_path = tmp_path / "test.wav"
        video_path.write_bytes(b"not a video")
        audio_path.write_bytes(b"not audio")

        result = compute_metrics(video_path, audio_path)

        # Tier 1 fields
        assert hasattr(result, "face_present_ratio")
        assert hasattr(result, "face_bbox_jitter")
        assert hasattr(result, "landmark_jitter")
        assert hasattr(result, "mouth_open_energy")
        assert hasattr(result, "mouth_audio_corr")
        assert hasattr(result, "blink_count")
        assert hasattr(result, "blink_rate_hz")

    def test_has_tier2_optional_fields(self, tmp_path):
        """Result has Tier 2 optional fields (null for now)."""
        video_path = tmp_path / "test.mp4"
        audio_path = tmp_path / "test.wav"
        video_path.write_bytes(b"not a video")
        audio_path.write_bytes(b"not audio")

        result = compute_metrics(video_path, audio_path)

        # Tier 2 fields (optional, null until SyncNet PR)
        assert hasattr(result, "lse_d")
        assert hasattr(result, "lse_c")
        assert result.lse_d is None
        assert result.lse_c is None

    def test_has_status_fields(self, tmp_path):
        """Result has status badge and reasons."""
        video_path = tmp_path / "test.mp4"
        audio_path = tmp_path / "test.wav"
        video_path.write_bytes(b"not a video")
        audio_path.write_bytes(b"not audio")

        result = compute_metrics(video_path, audio_path)

        assert hasattr(result, "status_badge")
        assert hasattr(result, "reasons")
        assert result.status_badge in ("pass", "flagged", "reject")
        assert isinstance(result.reasons, list)


class TestComputeMetricsFailureHandling:
    """Test graceful failure handling."""

    def test_invalid_video_returns_reject(self, tmp_path):
        """Invalid video file returns reject status."""
        video_path = tmp_path / "bad.mp4"
        audio_path = tmp_path / "test.wav"
        video_path.write_bytes(b"not a video")
        audio_path.write_bytes(b"not audio")

        result = compute_metrics(video_path, audio_path)

        assert result.decode_ok is False
        assert result.status_badge == "reject"

    def test_missing_video_returns_reject(self, tmp_path):
        """Missing video file returns reject status."""
        video_path = tmp_path / "missing.mp4"
        audio_path = tmp_path / "test.wav"
        audio_path.write_bytes(b"not audio")
        # video_path does not exist

        result = compute_metrics(video_path, audio_path)

        assert result.decode_ok is False
        assert result.status_badge == "reject"


class TestComputeMetricsValueRanges:
    """Test metric value ranges are valid."""

    def test_ratios_between_0_and_1(self, tmp_path):
        """Ratio metrics are in [0, 1]."""
        video_path = tmp_path / "test.mp4"
        audio_path = tmp_path / "test.wav"
        video_path.write_bytes(b"not a video")
        audio_path.write_bytes(b"not audio")

        result = compute_metrics(video_path, audio_path)

        assert 0.0 <= result.freeze_frame_ratio <= 1.0
        assert 0.0 <= result.face_present_ratio <= 1.0

    def test_durations_non_negative(self, tmp_path):
        """Duration metrics are non-negative."""
        video_path = tmp_path / "test.mp4"
        audio_path = tmp_path / "test.wav"
        video_path.write_bytes(b"not a video")
        audio_path.write_bytes(b"not audio")

        result = compute_metrics(video_path, audio_path)

        assert result.video_duration_ms >= 0
        assert result.audio_duration_ms >= 0
        assert result.av_duration_delta_ms >= 0

    def test_counts_non_negative(self, tmp_path):
        """Count metrics are non-negative."""
        video_path = tmp_path / "test.mp4"
        audio_path = tmp_path / "test.wav"
        video_path.write_bytes(b"not a video")
        audio_path.write_bytes(b"not audio")

        result = compute_metrics(video_path, audio_path)

        assert result.frame_count >= 0
        assert result.scene_cut_count >= 0
        assert result.frame_diff_spike_count >= 0


class TestComputeMetricsWithValidVideo:
    """Test with valid video (integration test, may be skipped)."""

    @pytest.mark.skip(reason="Requires ffmpeg and valid video file")
    def test_valid_video_computes_all_metrics(self, tmp_path):
        """Valid video produces meaningful metrics."""
        # This test requires a real video file and ffmpeg
        pass
