"""Database schema for Mirage.

Implements tables from DATA_MODEL.md with unique constraints
that enforce correctness invariants.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class DatasetItem(Base):
    """Source dataset items (video, audio, ref image)."""

    __tablename__ = "dataset_items"

    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_video_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    audio_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    ref_image_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class GenerationSpec(Base):
    """Generation configuration (model, prompt, params)."""

    __tablename__ = "generation_specs"

    generation_spec_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed_policy_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class Experiment(Base):
    """An experiment links a spec to a dataset."""

    __tablename__ = "experiments"

    experiment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    generation_spec_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("generation_specs.generation_spec_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class Run(Base):
    """A single variant execution within an experiment.

    Invariant: UNIQUE(experiment_id, item_id, variant_key)
    Ensures no duplicate runs for same experiment/item/variant.
    """

    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("experiments.experiment_id"), nullable=False
    )
    item_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("dataset_items.item_id"), nullable=False
    )
    variant_key: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    output_canon_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("experiment_id", "item_id", "variant_key", name="uq_run_identity"),
    )


class ProviderCall(Base):
    """Record of provider API calls for idempotency.

    Invariant: UNIQUE(provider, provider_idempotency_key)
    Prevents duplicate provider spend.
    """

    __tablename__ = "provider_calls"

    provider_call_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.run_id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    provider_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_json_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_json_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("provider", "provider_idempotency_key", name="uq_provider_idempotency"),
    )


class MetricResult(Base):
    """Computed metric values for a run.

    Invariant: UNIQUE(run_id, metric_name, metric_version)
    Allows different versions but prevents duplicate computation.
    """

    __tablename__ = "metric_results"

    metric_result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.run_id"), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(16), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("run_id", "metric_name", "metric_version", name="uq_metric_identity"),
    )


class HumanTask(Base):
    """Pairwise comparison task."""

    __tablename__ = "human_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    experiment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("experiments.experiment_id"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(String(16), nullable=False, default="pairwise")
    left_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.run_id"), nullable=False)
    right_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.run_id"), nullable=False)
    presented_left_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    presented_right_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    flip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class HumanRating(Base):
    """Human rating submission (append-only)."""

    __tablename__ = "human_ratings"

    rating_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("human_tasks.task_id"), nullable=False
    )
    rater_id: Mapped[str] = mapped_column(String(64), nullable=False)
    choice_realism: Mapped[str] = mapped_column(String(8), nullable=False)
    choice_lipsync: Mapped[str] = mapped_column(String(8), nullable=False)
    choice_targetmatch: Mapped[str | None] = mapped_column(String(8), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
