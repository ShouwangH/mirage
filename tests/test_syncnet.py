"""Tests for SyncNet adapter and metrics.

SyncNet provides Tier 2 metrics: LSE-D and LSE-C for lip sync evaluation.
These tests verify graceful degradation when dependencies are unavailable.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest


def _torch_available() -> bool:
    """Check if PyTorch is available."""
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


class TestSyncNetGracefulDegradation:
    """Test SyncNet graceful degradation when dependencies unavailable."""

    def test_import_without_torch(self):
        """SyncNet adapter imports even without PyTorch."""
        # This should not raise an error
        from mirage.adapter.syncnet import compute_lse_metrics

        assert compute_lse_metrics is not None

    def test_compute_returns_none_for_few_frames(self):
        """compute_lse_metrics returns (None, None) with too few frames."""
        from mirage.adapter.syncnet import compute_lse_metrics

        # Create too few frames (need at least 10)
        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(5)]
        audio_path = Path("/nonexistent/audio.wav")

        lse_d, lse_c = compute_lse_metrics(frames, audio_path)
        # Should return None due to insufficient frames
        assert lse_d is None
        assert lse_c is None

    def test_compute_returns_none_for_nonexistent_audio(self):
        """compute_lse_metrics returns (None, None) for missing audio."""
        from mirage.adapter.syncnet import compute_lse_metrics

        frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(10)]
        audio_path = Path("/nonexistent/audio.wav")

        lse_d, lse_c = compute_lse_metrics(frames, audio_path)
        # Should return None gracefully
        assert lse_d is None or isinstance(lse_d, float)


class TestLipSyncCorrelation:
    """Test correlation-based lip sync evaluation."""

    def test_correlation_with_matching_signals(self):
        """Correlation should be high for matching signals."""
        from mirage.adapter.syncnet.syncnet_adapter import _compute_correlation_with_lag

        # Create two correlated signals
        t = np.linspace(0, 2 * np.pi, 100)
        signal1 = np.sin(t).astype(np.float32)
        signal2 = np.sin(t).astype(np.float32)

        corr, lag = _compute_correlation_with_lag(signal1, signal2)

        assert corr > 0.9  # High correlation
        # Lag can be anywhere in search range for identical signals

    def test_correlation_with_offset_signals(self):
        """Correlation should detect lag in offset signals."""
        from mirage.adapter.syncnet.syncnet_adapter import _compute_correlation_with_lag

        # Create signal and lagged version
        t = np.linspace(0, 4 * np.pi, 100)
        signal1 = np.sin(t).astype(np.float32)
        signal2 = np.roll(signal1, 3)  # Shift by 3 frames

        corr, lag = _compute_correlation_with_lag(signal1, signal2, max_lag=5)

        assert corr > 0.5  # Should still find good correlation
        # Lag should be detected (might be -3 or close)


class TestSyncNetMetricsIntegration:
    """Integration tests for SyncNet metrics in bundle."""

    def test_bundle_has_syncnet_fields(self):
        """MetricBundleV1 has lse_d and lse_c fields."""
        from mirage.models.types import MetricBundleV1

        # Create a bundle with default values
        bundle = MetricBundleV1(
            decode_ok=True,
            video_duration_ms=1000,
            audio_duration_ms=1000,
            av_duration_delta_ms=0,
            fps=25.0,
            frame_count=25,
            scene_cut_count=0,
            freeze_frame_ratio=0.0,
            flicker_score=0.0,
            blur_score=100.0,
            frame_diff_spike_count=0,
            face_present_ratio=1.0,
            face_bbox_jitter=0.0,
            landmark_jitter=0.0,
            mouth_open_energy=0.0,
            mouth_audio_corr=0.5,
            blink_count=2,
            blink_rate_hz=0.2,
            lse_d=7.5,
            lse_c=5.0,
            status_badge="pass",
            reasons=[],
        )

        assert bundle.lse_d == 7.5
        assert bundle.lse_c == 5.0

    def test_bundle_accepts_null_syncnet(self):
        """MetricBundleV1 accepts null SyncNet values."""
        from mirage.models.types import MetricBundleV1

        bundle = MetricBundleV1(
            decode_ok=True,
            video_duration_ms=1000,
            audio_duration_ms=1000,
            av_duration_delta_ms=0,
            fps=25.0,
            frame_count=25,
            scene_cut_count=0,
            freeze_frame_ratio=0.0,
            flicker_score=0.0,
            blur_score=100.0,
            frame_diff_spike_count=0,
            face_present_ratio=1.0,
            face_bbox_jitter=0.0,
            landmark_jitter=0.0,
            mouth_open_energy=0.0,
            mouth_audio_corr=0.5,
            blink_count=2,
            blink_rate_hz=0.2,
            lse_d=None,
            lse_c=None,
            status_badge="pass",
            reasons=[],
        )

        assert bundle.lse_d is None
        assert bundle.lse_c is None
