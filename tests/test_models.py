"""Tests for pydantic models.

Tests validate:
1. Model creation with valid data
2. Model validation rejects invalid data
3. Literal type constraints enforced
4. Optional fields handled correctly
"""

import pytest
from pydantic import ValidationError

from mirage.models.types import (
    CanonArtifact,
    GenerationInput,
    HumanSummary,
    MetricBundleV1,
    RatingSubmission,
    RawArtifact,
    RunDetail,
)


class TestGenerationInput:
    """Test GenerationInput model."""

    def test_valid_generation_input(self):
        """Valid input should create model."""
        input_data = GenerationInput(
            provider="mock",
            model="test-model",
            model_version="1.0",
            prompt_template="Generate talking head",
            params={"temperature": 0.7},
            seed=42,
            input_audio_path="/path/to/audio.wav",
            input_audio_sha256="abc123",
            ref_image_path=None,
            ref_image_sha256=None,
        )
        assert input_data.provider == "mock"
        assert input_data.seed == 42

    def test_optional_ref_image(self):
        """ref_image fields should be optional."""
        input_data = GenerationInput(
            provider="mock",
            model="test-model",
            model_version=None,
            prompt_template="Generate talking head",
            params={},
            seed=42,
            input_audio_path="/path/to/audio.wav",
            input_audio_sha256="abc123",
            ref_image_path=None,
            ref_image_sha256=None,
        )
        assert input_data.ref_image_path is None


class TestRawArtifact:
    """Test RawArtifact model."""

    def test_valid_raw_artifact(self):
        """Valid artifact should create model."""
        artifact = RawArtifact(
            raw_video_path="/path/to/raw.mp4",
            provider_job_id="job-123",
            cost_usd=0.05,
            latency_ms=1500,
        )
        assert artifact.cost_usd == 0.05

    def test_optional_fields(self):
        """Optional fields should default to None."""
        artifact = RawArtifact(
            raw_video_path="/path/to/raw.mp4",
            provider_job_id=None,
            cost_usd=None,
            latency_ms=None,
        )
        assert artifact.cost_usd is None


class TestCanonArtifact:
    """Test CanonArtifact model."""

    def test_valid_canon_artifact(self):
        """Valid artifact should create model."""
        artifact = CanonArtifact(
            canon_video_path="/path/to/canon.mp4",
            sha256="abc123def456",
            duration_ms=5000,
        )
        assert artifact.duration_ms == 5000


class TestMetricBundleV1:
    """Test MetricBundleV1 model."""

    def test_valid_metric_bundle(self):
        """Valid metric bundle should create model."""
        bundle = MetricBundleV1(
            decode_ok=True,
            video_duration_ms=5000,
            audio_duration_ms=4950,
            av_duration_delta_ms=50,
            fps=30.0,
            frame_count=150,
            scene_cut_count=0,
            freeze_frame_ratio=0.01,
            flicker_score=0.02,
            blur_score=100.0,
            frame_diff_spike_count=0,
            face_present_ratio=0.98,
            face_bbox_jitter=0.01,
            landmark_jitter=0.02,
            mouth_open_energy=0.5,
            mouth_audio_corr=0.7,
            blink_count=5,
            blink_rate_hz=0.33,
            lse_d=None,
            lse_c=None,
            status_badge="pass",
            reasons=[],
        )
        assert bundle.decode_ok is True
        assert bundle.status_badge == "pass"

    def test_status_badge_validation(self):
        """status_badge must be pass/flagged/reject."""
        with pytest.raises(ValidationError):
            MetricBundleV1(
                decode_ok=True,
                video_duration_ms=5000,
                audio_duration_ms=5000,
                av_duration_delta_ms=0,
                fps=30.0,
                frame_count=150,
                scene_cut_count=0,
                freeze_frame_ratio=0.0,
                flicker_score=0.0,
                blur_score=100.0,
                frame_diff_spike_count=0,
                face_present_ratio=1.0,
                face_bbox_jitter=0.0,
                landmark_jitter=0.0,
                mouth_open_energy=0.5,
                mouth_audio_corr=0.8,
                blink_count=None,
                blink_rate_hz=None,
                lse_d=None,
                lse_c=None,
                status_badge="invalid",  # Invalid value
                reasons=[],
            )

    def test_optional_tier2_metrics(self):
        """Tier 2 metrics (syncnet) should be optional."""
        bundle = MetricBundleV1(
            decode_ok=True,
            video_duration_ms=5000,
            audio_duration_ms=5000,
            av_duration_delta_ms=0,
            fps=30.0,
            frame_count=150,
            scene_cut_count=0,
            freeze_frame_ratio=0.0,
            flicker_score=0.0,
            blur_score=100.0,
            frame_diff_spike_count=0,
            face_present_ratio=1.0,
            face_bbox_jitter=0.0,
            landmark_jitter=0.0,
            mouth_open_energy=0.5,
            mouth_audio_corr=0.8,
            blink_count=None,
            blink_rate_hz=None,
            lse_d=None,
            lse_c=None,
            status_badge="pass",
            reasons=[],
        )
        assert bundle.lse_d is None
        assert bundle.lse_c is None


class TestRunDetail:
    """Test RunDetail model."""

    def test_valid_run_detail(self):
        """Valid run detail should create model."""
        run = RunDetail(
            run_id="run-123",
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
            status="queued",
            output_canon_uri=None,
            output_sha256=None,
            metrics=None,
            status_badge=None,
            reasons=[],
        )
        assert run.status == "queued"

    def test_status_validation(self):
        """status must be queued/running/succeeded/failed."""
        with pytest.raises(ValidationError):
            RunDetail(
                run_id="run-123",
                experiment_id="exp-1",
                item_id="item-1",
                variant_key="seed=42",
                spec_hash="abc123",
                status="invalid_status",  # Invalid
                output_canon_uri=None,
                output_sha256=None,
                metrics=None,
                status_badge=None,
                reasons=[],
            )


class TestRatingSubmission:
    """Test RatingSubmission model."""

    def test_valid_rating(self):
        """Valid rating should create model."""
        rating = RatingSubmission(
            task_id="task-1",
            rater_id="rater-1",
            choice_realism="left",
            choice_lipsync="right",
            choice_targetmatch="tie",
            notes="Good quality",
        )
        assert rating.choice_realism == "left"

    def test_choice_validation(self):
        """Choices must be left/right/tie/skip."""
        with pytest.raises(ValidationError):
            RatingSubmission(
                task_id="task-1",
                rater_id="rater-1",
                choice_realism="invalid",  # Invalid
                choice_lipsync="right",
                choice_targetmatch=None,
                notes=None,
            )


class TestHumanSummary:
    """Test HumanSummary model."""

    def test_valid_summary(self):
        """Valid summary should create model."""
        summary = HumanSummary(
            win_rates={"seed=42": 0.75, "seed=43": 0.25},
            recommended_pick="seed=42",
            total_comparisons=4,
        )
        assert summary.win_rates["seed=42"] == 0.75

    def test_empty_win_rates(self):
        """Empty win rates should be valid."""
        summary = HumanSummary(
            win_rates={},
            recommended_pick=None,
            total_comparisons=0,
        )
        assert len(summary.win_rates) == 0
