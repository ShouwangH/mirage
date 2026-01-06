"""Tests for status badge derivation.

TDD: Tests written first per IMPLEMENTATION_PLAN.md.
"""

from mirage.metrics.status import (
    FLAG_BLUR_FLOOR,
    FLAG_FLICKER_CEILING,
    FLAG_FREEZE_CEILING,
    FLAG_MOUTH_AUDIO_CORR_FLOOR,
    REJECT_AV_DELTA_CEILING,
    REJECT_FACE_PRESENT_FLOOR,
    compute_status_badge,
)


class TestStatusBadgeRejectConditions:
    """Test reject (hard failure) conditions."""

    def test_decode_not_ok_returns_reject(self):
        """decode_ok = false triggers reject."""
        result = compute_status_badge(
            decode_ok=False,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] == "reject"
        assert "decode_ok=false" in result["reasons"]

    def test_low_face_present_returns_reject(self):
        """face_present_ratio below floor triggers reject."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.1,  # Below 0.2 floor
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] == "reject"
        assert any("face_present_ratio" in r for r in result["reasons"])

    def test_face_present_at_threshold_not_rejected(self):
        """face_present_ratio at exactly floor is not rejected."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=REJECT_FACE_PRESENT_FLOOR,  # Exactly at threshold
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] != "reject"

    def test_high_av_delta_returns_reject(self):
        """av_duration_delta_ms above ceiling triggers reject."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=600,  # Above 500ms ceiling
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] == "reject"
        assert any("av_duration_delta_ms" in r for r in result["reasons"])

    def test_av_delta_at_threshold_not_rejected(self):
        """av_duration_delta_ms at exactly ceiling is not rejected."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=REJECT_AV_DELTA_CEILING,  # Exactly at threshold
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] != "reject"

    def test_multiple_reject_reasons_collected(self):
        """Multiple reject conditions are all recorded."""
        result = compute_status_badge(
            decode_ok=False,
            face_present_ratio=0.1,
            av_duration_delta_ms=600,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] == "reject"
        assert len(result["reasons"]) == 3


class TestStatusBadgeFlagConditions:
    """Test flagged (review) conditions."""

    def test_high_flicker_returns_flagged(self):
        """High flicker_score triggers flagged."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=FLAG_FLICKER_CEILING + 1,  # Above threshold
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] == "flagged"
        assert any("flicker_score" in r for r in result["reasons"])

    def test_high_freeze_frame_ratio_returns_flagged(self):
        """High freeze_frame_ratio triggers flagged."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=FLAG_FREEZE_CEILING + 0.1,  # Above threshold
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] == "flagged"
        assert any("freeze_frame_ratio" in r for r in result["reasons"])

    def test_low_blur_score_returns_flagged(self):
        """Low blur_score triggers flagged."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=FLAG_BLUR_FLOOR - 1,  # Below threshold
            mouth_audio_corr=0.5,
        )
        assert result["badge"] == "flagged"
        assert any("blur_score" in r for r in result["reasons"])

    def test_low_mouth_audio_corr_returns_flagged(self):
        """Low mouth_audio_corr triggers flagged."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=FLAG_MOUTH_AUDIO_CORR_FLOOR - 0.1,  # Below threshold
        )
        assert result["badge"] == "flagged"
        assert any("mouth_audio_corr" in r for r in result["reasons"])

    def test_multiple_flag_reasons_collected(self):
        """Multiple flag conditions are all recorded."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=FLAG_FLICKER_CEILING + 1,
            freeze_frame_ratio=FLAG_FREEZE_CEILING + 0.1,
            blur_score=FLAG_BLUR_FLOOR - 1,
            mouth_audio_corr=FLAG_MOUTH_AUDIO_CORR_FLOOR - 0.1,
        )
        assert result["badge"] == "flagged"
        assert len(result["reasons"]) == 4


class TestStatusBadgePassConditions:
    """Test pass conditions."""

    def test_all_good_metrics_returns_pass(self):
        """Good metrics return pass with no reasons."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] == "pass"
        assert result["reasons"] == []

    def test_metrics_at_safe_boundaries_returns_pass(self):
        """Metrics at safe boundary values return pass."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=REJECT_FACE_PRESENT_FLOOR,  # At floor
            av_duration_delta_ms=REJECT_AV_DELTA_CEILING,  # At ceiling
            flicker_score=FLAG_FLICKER_CEILING,  # At ceiling
            freeze_frame_ratio=FLAG_FREEZE_CEILING,  # At ceiling
            blur_score=FLAG_BLUR_FLOOR,  # At floor
            mouth_audio_corr=FLAG_MOUTH_AUDIO_CORR_FLOOR,  # At floor
        )
        assert result["badge"] == "pass"
        assert result["reasons"] == []


class TestStatusBadgePriority:
    """Test priority of reject over flagged."""

    def test_reject_takes_priority_over_flagged(self):
        """Reject conditions override flagged conditions."""
        result = compute_status_badge(
            decode_ok=False,  # Reject condition
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=FLAG_FLICKER_CEILING + 1,  # Flag condition
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] == "reject"
        # Both reasons should be present
        assert any("decode_ok" in r for r in result["reasons"])
        assert any("flicker_score" in r for r in result["reasons"])


class TestStatusBadgeReturn:
    """Test return value structure."""

    def test_return_has_badge_key(self):
        """Result has 'badge' key."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert "badge" in result

    def test_return_has_reasons_key(self):
        """Result has 'reasons' key."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert "reasons" in result
        assert isinstance(result["reasons"], list)

    def test_badge_is_literal_type(self):
        """Badge is one of pass/flagged/reject."""
        result = compute_status_badge(
            decode_ok=True,
            face_present_ratio=0.9,
            av_duration_delta_ms=100,
            flicker_score=1.0,
            freeze_frame_ratio=0.0,
            blur_score=100.0,
            mouth_audio_corr=0.5,
        )
        assert result["badge"] in ("pass", "flagged", "reject")
