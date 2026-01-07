"""Domain models for Mirage.

Pure Python dataclasses representing domain entities.
These models are independent of SQLAlchemy and used throughout
the application for clean separation from the database layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


# ============================================================================
# Run Domain
# ============================================================================

RunStatus = Literal["queued", "running", "succeeded", "failed"]


@dataclass
class RunEntity:
    """Domain model for a run."""

    run_id: str
    experiment_id: str
    item_id: str
    variant_key: str
    spec_hash: str
    status: RunStatus
    output_canon_uri: str | None = None
    output_sha256: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error_code: str | None = None
    error_detail: str | None = None


# ============================================================================
# Human Evaluation Domain
# ============================================================================

TaskStatus = Literal["open", "assigned", "done", "void"]
Choice = Literal["left", "right", "tie", "skip"]


@dataclass
class TaskEntity:
    """Domain model for a human evaluation task."""

    task_id: str
    experiment_id: str
    task_type: str
    left_run_id: str
    right_run_id: str
    presented_left_run_id: str
    presented_right_run_id: str
    flip: bool
    status: TaskStatus


@dataclass
class RatingEntity:
    """Domain model for a human rating."""

    rating_id: str
    task_id: str
    rater_id: str
    choice_realism: Choice
    choice_lipsync: Choice
    choice_targetmatch: Choice | None = None
    notes: str | None = None


# ============================================================================
# Provider Call Domain
# ============================================================================

ProviderCallStatus = Literal["created", "completed", "failed"]


@dataclass
class ProviderCallEntity:
    """Domain model for a provider API call."""

    provider_call_id: str
    run_id: str
    provider: str
    provider_idempotency_key: str
    attempt: int
    status: ProviderCallStatus
    provider_job_id: str | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None


# ============================================================================
# Metric Result Domain
# ============================================================================


@dataclass
class MetricResultEntity:
    """Domain model for a metric result."""

    metric_result_id: str
    run_id: str
    metric_name: str
    metric_version: str
    value_json: str
    status: str
    error_detail: str | None = None


# ============================================================================
# Dataset Domain
# ============================================================================


@dataclass
class DatasetItemEntity:
    """Domain model for a dataset item."""

    item_id: str
    subject_id: str
    source_video_uri: str
    audio_uri: str
    ref_image_uri: str | None = None


# ============================================================================
# Experiment Domain
# ============================================================================


@dataclass
class ExperimentEntity:
    """Domain model for an experiment."""

    experiment_id: str
    generation_spec_id: str
    status: str


@dataclass
class GenerationSpecEntity:
    """Domain model for a generation spec."""

    generation_spec_id: str
    provider: str
    model: str
    prompt_template: str
    model_version: str | None = None
    params_json: str | None = None
