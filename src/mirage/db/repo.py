"""Repository pattern for database operations.

Encapsulates all SQLAlchemy queries, keeping domain logic pure.
Returns domain models (not SQLAlchemy entities) to external callers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from mirage.models.domain import (
    DatasetItemEntity,
    ExperimentEntity,
    GenerationSpecEntity,
    MetricResultEntity,
    ProviderCallEntity,
    RatingEntity,
    RunEntity,
    TaskEntity,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DbSession
else:
    DbSession = Session

# Re-export for external use
__all__ = ["DbSession"]


# ============================================================================
# Converters: SQLAlchemy -> Domain
# ============================================================================


def _run_to_entity(run: Run) -> RunEntity:
    """Convert SQLAlchemy Run to domain entity."""
    return RunEntity(
        run_id=run.run_id,
        experiment_id=run.experiment_id,
        item_id=run.item_id,
        variant_key=run.variant_key,
        spec_hash=run.spec_hash,
        status=run.status,
        output_canon_uri=run.output_canon_uri,
        output_sha256=run.output_sha256,
        started_at=run.started_at,
        ended_at=run.ended_at,
        error_code=run.error_code,
        error_detail=run.error_detail,
    )


def _task_to_entity(task: HumanTask) -> TaskEntity:
    """Convert SQLAlchemy HumanTask to domain entity."""
    return TaskEntity(
        task_id=task.task_id,
        experiment_id=task.experiment_id,
        task_type=task.task_type,
        left_run_id=task.left_run_id,
        right_run_id=task.right_run_id,
        presented_left_run_id=task.presented_left_run_id,
        presented_right_run_id=task.presented_right_run_id,
        flip=task.flip,
        status=task.status,
    )


def _rating_to_entity(rating: HumanRating) -> RatingEntity:
    """Convert SQLAlchemy HumanRating to domain entity."""
    return RatingEntity(
        rating_id=rating.rating_id,
        task_id=rating.task_id,
        rater_id=rating.rater_id,
        choice_realism=rating.choice_realism,
        choice_lipsync=rating.choice_lipsync,
        choice_targetmatch=rating.choice_targetmatch,
        notes=rating.notes,
    )


def _experiment_to_entity(exp: Experiment) -> ExperimentEntity:
    """Convert SQLAlchemy Experiment to domain entity."""
    return ExperimentEntity(
        experiment_id=exp.experiment_id,
        generation_spec_id=exp.generation_spec_id,
        status=exp.status,
    )


def _spec_to_entity(spec: GenerationSpec) -> GenerationSpecEntity:
    """Convert SQLAlchemy GenerationSpec to domain entity."""
    return GenerationSpecEntity(
        generation_spec_id=spec.generation_spec_id,
        provider=spec.provider,
        model=spec.model,
        model_version=spec.model_version,
        prompt_template=spec.prompt_template,
        params_json=spec.params_json,
    )


def _dataset_item_to_entity(item: DatasetItem) -> DatasetItemEntity:
    """Convert SQLAlchemy DatasetItem to domain entity."""
    return DatasetItemEntity(
        item_id=item.item_id,
        subject_id=item.subject_id,
        source_video_uri=item.source_video_uri,
        audio_uri=item.audio_uri,
        ref_image_uri=item.ref_image_uri,
    )


def _provider_call_to_entity(call: ProviderCall) -> ProviderCallEntity:
    """Convert SQLAlchemy ProviderCall to domain entity."""
    return ProviderCallEntity(
        provider_call_id=call.provider_call_id,
        run_id=call.run_id,
        provider=call.provider,
        provider_idempotency_key=call.provider_idempotency_key,
        attempt=call.attempt,
        status=call.status,
        provider_job_id=call.provider_job_id,
        cost_usd=call.cost_usd,
        latency_ms=call.latency_ms,
    )


def _metric_result_to_entity(result: MetricResult) -> MetricResultEntity:
    """Convert SQLAlchemy MetricResult to domain entity."""
    return MetricResultEntity(
        metric_result_id=result.metric_result_id,
        run_id=result.run_id,
        metric_name=result.metric_name,
        metric_version=result.metric_version,
        value_json=result.value_json,
        status=result.status,
        error_detail=result.error_detail,
    )


# ============================================================================
# Experiment Repository
# ============================================================================


def get_experiment(session: DbSession, experiment_id: str) -> ExperimentEntity | None:
    """Get experiment by ID."""
    exp = session.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()
    return _experiment_to_entity(exp) if exp else None


def get_generation_spec(session: DbSession, spec_id: str) -> GenerationSpecEntity | None:
    """Get generation spec by ID."""
    spec = (
        session.query(GenerationSpec).filter(GenerationSpec.generation_spec_id == spec_id).first()
    )
    return _spec_to_entity(spec) if spec else None


# ============================================================================
# Run Repository
# ============================================================================


def get_run(session: DbSession, run_id: str) -> RunEntity | None:
    """Get run by ID."""
    run = session.query(Run).filter(Run.run_id == run_id).first()
    return _run_to_entity(run) if run else None


def get_runs_for_experiment(session: DbSession, experiment_id: str) -> list[RunEntity]:
    """Get all runs for an experiment."""
    runs = session.query(Run).filter(Run.experiment_id == experiment_id).all()
    return [_run_to_entity(r) for r in runs]


def get_succeeded_runs_for_experiment(session: DbSession, experiment_id: str) -> list[RunEntity]:
    """Get all succeeded runs for an experiment."""
    runs = (
        session.query(Run)
        .filter(
            Run.experiment_id == experiment_id,
            Run.status == "succeeded",
        )
        .all()
    )
    return [_run_to_entity(r) for r in runs]


def get_run_ids_for_experiment(session: DbSession, experiment_id: str) -> list[str]:
    """Get all run IDs for an experiment."""
    runs = session.query(Run.run_id).filter(Run.experiment_id == experiment_id).all()
    return [r[0] for r in runs]


def get_succeeded_run_ids_for_experiment(session: DbSession, experiment_id: str) -> list[str]:
    """Get succeeded run IDs for an experiment."""
    runs = (
        session.query(Run.run_id)
        .filter(Run.experiment_id == experiment_id, Run.status == "succeeded")
        .all()
    )
    return [r[0] for r in runs]


def get_queued_runs(session: DbSession) -> list[RunEntity]:
    """Get all runs with status=queued."""
    runs = session.query(Run).filter(Run.status == "queued").all()
    return [_run_to_entity(r) for r in runs]


def update_run_status(
    session: DbSession,
    run_id: str,
    status: str,
    *,
    output_canon_uri: str | None = None,
    output_sha256: str | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Update run status and optional fields."""
    run = session.query(Run).filter(Run.run_id == run_id).first()
    if run:
        run.status = status
        if output_canon_uri is not None:
            run.output_canon_uri = output_canon_uri
        if output_sha256 is not None:
            run.output_sha256 = output_sha256
        if error_code is not None:
            run.error_code = error_code
        if error_detail is not None:
            run.error_detail = error_detail


def set_run_started(session: DbSession, run_id: str) -> None:
    """Set run started_at timestamp."""
    from datetime import datetime, timezone

    run = session.query(Run).filter(Run.run_id == run_id).first()
    if run:
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)


def set_run_ended(session: DbSession, run_id: str) -> None:
    """Set run ended_at timestamp."""
    from datetime import datetime, timezone

    run = session.query(Run).filter(Run.run_id == run_id).first()
    if run:
        run.ended_at = datetime.now(timezone.utc)


# ============================================================================
# Dataset Repository
# ============================================================================


def get_dataset_item(session: DbSession, item_id: str) -> DatasetItemEntity | None:
    """Get dataset item by ID."""
    item = session.query(DatasetItem).filter(DatasetItem.item_id == item_id).first()
    return _dataset_item_to_entity(item) if item else None


# ============================================================================
# Metrics Repository
# ============================================================================


def get_metric_result(
    session: DbSession, run_id: str, metric_name: str = "MetricBundleV1"
) -> MetricResultEntity | None:
    """Get metric result for a run."""
    result = (
        session.query(MetricResult)
        .filter(
            MetricResult.run_id == run_id,
            MetricResult.metric_name == metric_name,
        )
        .first()
    )
    return _metric_result_to_entity(result) if result else None


def create_metric_result(session: DbSession, entity: MetricResultEntity) -> MetricResultEntity:
    """Create a new metric result."""
    result = MetricResult(
        metric_result_id=entity.metric_result_id,
        run_id=entity.run_id,
        metric_name=entity.metric_name,
        metric_version=entity.metric_version,
        value_json=entity.value_json,
        status=entity.status,
        error_detail=entity.error_detail,
    )
    session.add(result)
    return entity


# ============================================================================
# Task Repository
# ============================================================================


def get_tasks_for_experiment(session: DbSession, experiment_id: str) -> list[TaskEntity]:
    """Get all tasks for an experiment."""
    tasks = session.query(HumanTask).filter(HumanTask.experiment_id == experiment_id).all()
    return [_task_to_entity(t) for t in tasks]


def get_done_tasks_for_experiment(session: DbSession, experiment_id: str) -> list[TaskEntity]:
    """Get completed tasks for an experiment."""
    tasks = (
        session.query(HumanTask)
        .filter(
            HumanTask.experiment_id == experiment_id,
            HumanTask.status == "done",
        )
        .all()
    )
    return [_task_to_entity(t) for t in tasks]


def get_open_task_for_experiment(session: DbSession, experiment_id: str) -> TaskEntity | None:
    """Get next open task for an experiment."""
    task = (
        session.query(HumanTask)
        .filter(
            HumanTask.experiment_id == experiment_id,
            HumanTask.status == "open",
        )
        .first()
    )
    return _task_to_entity(task) if task else None


def get_existing_task_pairs(session: DbSession, experiment_id: str) -> set[tuple[str, str]]:
    """Get existing task pairs (order-independent) for an experiment."""
    tasks = session.query(HumanTask).filter(HumanTask.experiment_id == experiment_id).all()
    return {tuple(sorted([t.left_run_id, t.right_run_id])) for t in tasks}


def create_task(session: DbSession, entity: TaskEntity) -> TaskEntity:
    """Create a new task."""
    task = HumanTask(
        task_id=entity.task_id,
        experiment_id=entity.experiment_id,
        task_type=entity.task_type,
        left_run_id=entity.left_run_id,
        right_run_id=entity.right_run_id,
        presented_left_run_id=entity.presented_left_run_id,
        presented_right_run_id=entity.presented_right_run_id,
        flip=entity.flip,
        status=entity.status,
    )
    session.add(task)
    return entity


def update_task_status(session: DbSession, task_id: str, status: str) -> None:
    """Update task status."""
    task = session.query(HumanTask).filter(HumanTask.task_id == task_id).first()
    if task:
        task.status = status


# ============================================================================
# Rating Repository
# ============================================================================


def get_task(session: DbSession, task_id: str) -> TaskEntity | None:
    """Get task by ID."""
    task = session.query(HumanTask).filter(HumanTask.task_id == task_id).first()
    return _task_to_entity(task) if task else None


def get_ratings_for_task(session: DbSession, task_id: str) -> list[RatingEntity]:
    """Get all ratings for a task."""
    ratings = session.query(HumanRating).filter(HumanRating.task_id == task_id).all()
    return [_rating_to_entity(r) for r in ratings]


def create_rating(session: DbSession, entity: RatingEntity) -> RatingEntity:
    """Create a new rating."""
    rating = HumanRating(
        rating_id=entity.rating_id,
        task_id=entity.task_id,
        rater_id=entity.rater_id,
        choice_realism=entity.choice_realism,
        choice_lipsync=entity.choice_lipsync,
        choice_targetmatch=entity.choice_targetmatch,
        notes=entity.notes,
    )
    session.add(rating)
    return entity


# ============================================================================
# Summary / Aggregation Repository
# ============================================================================


def get_ratings_for_tasks(session: DbSession, task_ids: list[str]) -> list[RatingEntity]:
    """Get all ratings for a list of tasks."""
    if not task_ids:
        return []
    ratings = session.query(HumanRating).filter(HumanRating.task_id.in_(task_ids)).all()
    return [_rating_to_entity(r) for r in ratings]


# ============================================================================
# Provider Call Repository
# ============================================================================


def get_provider_call_by_idempotency_key(
    session: DbSession, provider: str, idempotency_key: str
) -> ProviderCallEntity | None:
    """Get provider call by provider and idempotency key."""
    call = (
        session.query(ProviderCall)
        .filter(
            ProviderCall.provider == provider,
            ProviderCall.provider_idempotency_key == idempotency_key,
        )
        .first()
    )
    return _provider_call_to_entity(call) if call else None


def create_provider_call(session: DbSession, entity: ProviderCallEntity) -> ProviderCallEntity:
    """Create a new provider call."""
    call = ProviderCall(
        provider_call_id=entity.provider_call_id,
        run_id=entity.run_id,
        provider=entity.provider,
        provider_idempotency_key=entity.provider_idempotency_key,
        attempt=entity.attempt,
        status=entity.status,
        provider_job_id=entity.provider_job_id,
        cost_usd=entity.cost_usd,
        latency_ms=entity.latency_ms,
    )
    session.add(call)
    return entity


def update_provider_call(
    session: DbSession,
    provider_call_id: str,
    *,
    status: str | None = None,
    provider_job_id: str | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
) -> None:
    """Update provider call fields."""
    call = (
        session.query(ProviderCall).filter(ProviderCall.provider_call_id == provider_call_id).first()
    )
    if call:
        if status is not None:
            call.status = status
        if provider_job_id is not None:
            call.provider_job_id = provider_job_id
        if cost_usd is not None:
            call.cost_usd = cost_usd
        if latency_ms is not None:
            call.latency_ms = latency_ms


# ============================================================================
# Batch Operations
# ============================================================================


def commit(session: DbSession) -> None:
    """Commit current transaction."""
    session.commit()
