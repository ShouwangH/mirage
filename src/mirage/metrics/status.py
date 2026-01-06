"""Status badge derivation from metrics.

Based on METRICS.md:
- reject: hard failure (decode fail, no face, A/V desync)
- flagged: review signals (flicker, freeze, blur, lip-sync issues)
- pass: not reject and not flagged

Thresholds are demo-tuned and should be labeled as "review signals" in UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Reject thresholds (hard failure)
REJECT_FACE_PRESENT_FLOOR = 0.2  # Below this = reject
REJECT_AV_DELTA_CEILING = 500  # Above this (ms) = reject

# Flag thresholds (review)
FLAG_FLICKER_CEILING = 10.0  # Above this = flagged
FLAG_FREEZE_CEILING = 0.3  # Above this = flagged
FLAG_BLUR_FLOOR = 20.0  # Below this = flagged (blurry)
FLAG_MOUTH_AUDIO_CORR_FLOOR = -0.1  # Below this = flagged (poor lip-sync)

StatusBadge = Literal["pass", "flagged", "reject"]


@dataclass
class StatusResult:
    """Result of status badge computation.

    Attributes:
        badge: One of 'pass', 'flagged', or 'reject'.
        reasons: List of human-readable reason strings.
    """

    badge: StatusBadge
    reasons: list[str] = field(default_factory=list)


def compute_status_badge(
    decode_ok: bool,
    face_present_ratio: float,
    av_duration_delta_ms: int,
    flicker_score: float,
    freeze_frame_ratio: float,
    blur_score: float,
    mouth_audio_corr: float,
) -> StatusResult:
    """Compute status badge and reasons from metrics.

    Args:
        decode_ok: Whether video can be decoded.
        face_present_ratio: Ratio of frames with detected face [0,1].
        av_duration_delta_ms: Absolute difference between audio/video duration.
        flicker_score: Luminance instability (higher = more flicker).
        freeze_frame_ratio: Ratio of frozen frames [0,1].
        blur_score: Variance of Laplacian (higher = sharper).
        mouth_audio_corr: Correlation between mouth and audio [-1,1].

    Returns:
        StatusResult with badge and reasons.
    """
    reasons: list[str] = []
    has_reject = False
    has_flag = False

    # Reject conditions (hard failure)
    if not decode_ok:
        reasons.append("decode_ok=false")
        has_reject = True

    if face_present_ratio < REJECT_FACE_PRESENT_FLOOR:
        reasons.append(f"face_present_ratio={face_present_ratio:.2f} < {REJECT_FACE_PRESENT_FLOOR}")
        has_reject = True

    if av_duration_delta_ms > REJECT_AV_DELTA_CEILING:
        reasons.append(f"av_duration_delta_ms={av_duration_delta_ms} > {REJECT_AV_DELTA_CEILING}")
        has_reject = True

    # Flag conditions (review)
    if flicker_score > FLAG_FLICKER_CEILING:
        reasons.append(f"flicker_score={flicker_score:.2f} > {FLAG_FLICKER_CEILING}")
        has_flag = True

    if freeze_frame_ratio > FLAG_FREEZE_CEILING:
        reasons.append(f"freeze_frame_ratio={freeze_frame_ratio:.2f} > {FLAG_FREEZE_CEILING}")
        has_flag = True

    if blur_score < FLAG_BLUR_FLOOR:
        reasons.append(f"blur_score={blur_score:.2f} < {FLAG_BLUR_FLOOR}")
        has_flag = True

    if mouth_audio_corr < FLAG_MOUTH_AUDIO_CORR_FLOOR:
        reasons.append(f"mouth_audio_corr={mouth_audio_corr:.2f} < {FLAG_MOUTH_AUDIO_CORR_FLOOR}")
        has_flag = True

    # Determine badge (reject > flagged > pass)
    if has_reject:
        badge: StatusBadge = "reject"
    elif has_flag:
        badge = "flagged"
    else:
        badge = "pass"

    return StatusResult(badge=badge, reasons=reasons)
