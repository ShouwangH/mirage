"""Repository pattern for database operations.

Encapsulates all SQLAlchemy queries, keeping domain logic pure.
All methods take a Session and return typed domain objects or primitives.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from mirage.db.schema import (
    DatasetItem,
    Experiment,
    GenerationSpec,
    HumanRating,
    HumanTask,
    MetricResult,
    ProviderCall,
    Run,
)

# ============================================================================
# Experiment Repository
# ============================================================================


def get_experiment(session: Session, experiment_id: str) -> Experiment | None:
    """Get experiment by ID."""
    return session.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()


def get_generation_spec(session: Session, spec_id: str) -> GenerationSpec | None:
    """Get generation spec by ID."""
    return (
        session.query(GenerationSpec).filter(GenerationSpec.generation_spec_id == spec_id).first()
    )


# ============================================================================
# Run Repository
# ============================================================================


def get_run(session: Session, run_id: str) -> Run | None:
    """Get run by ID."""
    return session.query(Run).filter(Run.run_id == run_id).first()


def get_runs_for_experiment(session: Session, experiment_id: str) -> list[Run]:
    """Get all runs for an experiment."""
    return session.query(Run).filter(Run.experiment_id == experiment_id).all()


def get_succeeded_runs_for_experiment(session: Session, experiment_id: str) -> list[Run]:
    """Get all succeeded runs for an experiment."""
    return (
        session.query(Run)
        .filter(
            Run.experiment_id == experiment_id,
            Run.status == "succeeded",
        )
        .all()
    )


def get_run_ids_for_experiment(session: Session, experiment_id: str) -> list[str]:
    """Get all run IDs for an experiment."""
    runs = get_runs_for_experiment(session, experiment_id)
    return [run.run_id for run in runs]


def get_succeeded_run_ids_for_experiment(session: Session, experiment_id: str) -> list[str]:
    """Get succeeded run IDs for an experiment."""
    runs = get_succeeded_runs_for_experiment(session, experiment_id)
    return [run.run_id for run in runs]


def get_queued_runs(session: Session) -> list[Run]:
    """Get all runs with status=queued."""
    return session.query(Run).filter(Run.status == "queued").all()


# ============================================================================
# Dataset Repository
# ============================================================================


def get_dataset_item(session: Session, item_id: str) -> DatasetItem | None:
    """Get dataset item by ID."""
    return session.query(DatasetItem).filter(DatasetItem.item_id == item_id).first()


# ============================================================================
# Metrics Repository
# ============================================================================


def get_metric_result(
    session: Session, run_id: str, metric_name: str = "MetricBundleV1"
) -> MetricResult | None:
    """Get metric result for a run."""
    return (
        session.query(MetricResult)
        .filter(
            MetricResult.run_id == run_id,
            MetricResult.metric_name == metric_name,
        )
        .first()
    )


# ============================================================================
# Task Repository
# ============================================================================


@dataclass
class TaskPair:
    """Represents a pair of run IDs for comparison."""

    left_run_id: str
    right_run_id: str


def get_tasks_for_experiment(session: Session, experiment_id: str) -> list[HumanTask]:
    """Get all tasks for an experiment."""
    return session.query(HumanTask).filter(HumanTask.experiment_id == experiment_id).all()


def get_done_tasks_for_experiment(session: Session, experiment_id: str) -> list[HumanTask]:
    """Get completed tasks for an experiment."""
    return (
        session.query(HumanTask)
        .filter(
            HumanTask.experiment_id == experiment_id,
            HumanTask.status == "done",
        )
        .all()
    )


def get_open_task_for_experiment(session: Session, experiment_id: str) -> HumanTask | None:
    """Get next open task for an experiment."""
    return (
        session.query(HumanTask)
        .filter(
            HumanTask.experiment_id == experiment_id,
            HumanTask.status == "open",
        )
        .first()
    )


def get_existing_task_pairs(session: Session, experiment_id: str) -> set[tuple[str, str]]:
    """Get existing task pairs (order-independent) for an experiment."""
    tasks = get_tasks_for_experiment(session, experiment_id)
    return {tuple(sorted([t.left_run_id, t.right_run_id])) for t in tasks}


def create_task(session: Session, task: HumanTask) -> HumanTask:
    """Create a new task."""
    session.add(task)
    return task


def update_task_status(session: Session, task_id: str, status: str) -> HumanTask | None:
    """Update task status."""
    task = session.query(HumanTask).filter(HumanTask.task_id == task_id).first()
    if task:
        task.status = status
    return task


# ============================================================================
# Rating Repository
# ============================================================================


def get_task(session: Session, task_id: str) -> HumanTask | None:
    """Get task by ID."""
    return session.query(HumanTask).filter(HumanTask.task_id == task_id).first()


def get_ratings_for_task(session: Session, task_id: str) -> list[HumanRating]:
    """Get all ratings for a task."""
    return session.query(HumanRating).filter(HumanRating.task_id == task_id).all()


def create_rating(session: Session, rating: HumanRating) -> HumanRating:
    """Create a new rating."""
    session.add(rating)
    return rating


# ============================================================================
# Summary / Aggregation Repository
# ============================================================================


def get_ratings_for_tasks(session: Session, task_ids: list[str]) -> list[HumanRating]:
    """Get all ratings for a list of tasks."""
    if not task_ids:
        return []
    return session.query(HumanRating).filter(HumanRating.task_id.in_(task_ids)).all()


# ============================================================================
# Provider Call Repository
# ============================================================================


def get_provider_call_by_idempotency_key(
    session: Session, provider: str, idempotency_key: str
) -> ProviderCall | None:
    """Get provider call by provider and idempotency key."""
    return (
        session.query(ProviderCall)
        .filter(
            ProviderCall.provider == provider,
            ProviderCall.provider_idempotency_key == idempotency_key,
        )
        .first()
    )


def create_provider_call(session: Session, provider_call: ProviderCall) -> ProviderCall:
    """Create a new provider call."""
    session.add(provider_call)
    return provider_call


# ============================================================================
# Metric Result Repository
# ============================================================================


def create_metric_result(session: Session, metric_result: MetricResult) -> MetricResult:
    """Create a new metric result."""
    session.add(metric_result)
    return metric_result


# ============================================================================
# Batch Operations
# ============================================================================


def commit(session: Session) -> None:
    """Commit current transaction."""
    session.commit()
