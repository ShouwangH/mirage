"""Pydantic models for Mirage API.

These models are frozen per IMPLEMENTATION_PLAN.md.
Changes require updating API.md and METRICS.md.
"""

from typing import Literal

from pydantic import BaseModel


class GenerationInput(BaseModel):
    """Input for generation provider."""

    provider: str
    model: str
    model_version: str | None
    prompt_template: str
    params: dict
    seed: int
    input_audio_path: str
    input_audio_sha256: str
    ref_image_path: str | None
    ref_image_sha256: str | None


class RawArtifact(BaseModel):
    """Raw output from provider before normalization."""

    raw_video_path: str
    provider_job_id: str | None
    cost_usd: float | None
    latency_ms: int | None


class CanonArtifact(BaseModel):
    """Normalized canonical artifact."""

    canon_video_path: str
    sha256: str
    duration_ms: int


class MetricBundleV1(BaseModel):
    """Complete metric bundle (v1).

    All metrics run on output_canon.mp4 and canonical audio.
    """

    # Tier 0 (ffmpeg/opencv/numpy)
    decode_ok: bool
    video_duration_ms: int
    audio_duration_ms: int
    av_duration_delta_ms: int
    fps: float
    frame_count: int
    scene_cut_count: int
    freeze_frame_ratio: float
    flicker_score: float
    blur_score: float
    frame_diff_spike_count: int

    # Tier 1 (mediapipe)
    face_present_ratio: float
    face_bbox_jitter: float
    landmark_jitter: float
    mouth_open_energy: float
    mouth_audio_corr: float
    blink_count: int | None
    blink_rate_hz: float | None

    # Tier 2 (optional, syncnet)
    lse_d: float | None
    lse_c: float | None

    # Status
    status_badge: Literal["pass", "flagged", "reject"]
    reasons: list[str]


class GenerationSpecDetail(BaseModel):
    """Generation spec details for API response."""

    generation_spec_id: str
    provider: str
    model: str
    model_version: str | None
    prompt_template: str
    params: dict | None


class DatasetItemDetail(BaseModel):
    """Dataset item details for API response."""

    item_id: str
    subject_id: str
    source_video_uri: str
    audio_uri: str
    ref_image_uri: str | None


class RunDetail(BaseModel):
    """Run details for API response."""

    run_id: str
    experiment_id: str
    item_id: str
    variant_key: str
    spec_hash: str
    status: Literal["queued", "running", "succeeded", "failed"]
    output_canon_uri: str | None
    output_sha256: str | None
    metrics: MetricBundleV1 | None
    status_badge: Literal["pass", "flagged", "reject"] | None
    reasons: list[str]


class HumanSummary(BaseModel):
    """Summary of human evaluation results."""

    win_rates: dict[str, float]  # variant_key -> win_rate
    recommended_pick: str | None  # variant_key
    total_comparisons: int


class ExperimentOverview(BaseModel):
    """Full experiment overview for API response."""

    experiment_id: str
    status: Literal["draft", "running", "complete"]
    generation_spec: GenerationSpecDetail
    dataset_item: DatasetItemDetail
    runs: list[RunDetail]
    human_summary: HumanSummary | None


class RatingSubmission(BaseModel):
    """Human rating submission."""

    task_id: str
    rater_id: str
    choice_realism: Literal["left", "right", "tie", "skip"]
    choice_lipsync: Literal["left", "right", "tie", "skip"]
    choice_targetmatch: Literal["left", "right", "tie", "skip"] | None
    notes: str | None


class TaskDetail(BaseModel):
    """Pairwise task details for API response."""

    task_id: str
    experiment_id: str
    left_run_id: str
    right_run_id: str
    presented_left_run_id: str
    presented_right_run_id: str
    flip: bool
    status: Literal["open", "assigned", "done", "void"]
