"""Experiments API endpoint.

GET /api/experiments/{experiment_id} - Get experiment overview
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from mirage.api.app import get_db_session
from mirage.db import repo
from mirage.db.repo import DbSession
from mirage.models.domain import RunEntity
from mirage.models.types import (
    DatasetItemDetail,
    ExperimentOverview,
    GenerationSpecDetail,
    MetricBundleV1,
    RunDetail,
)

router = APIRouter()


def _build_run_detail(session: DbSession, run: RunEntity) -> RunDetail:
    """Build RunDetail from RunEntity.

    Args:
        session: Database session.
        run: Run entity.

    Returns:
        RunDetail model.
    """
    # Get metrics if available via repository
    metrics = None
    status_badge = None
    reasons: list[str] = []

    metric_result = repo.get_metric_result(session, run.run_id)

    if metric_result and metric_result.value_json:
        try:
            metrics_data = json.loads(metric_result.value_json)
            metrics = MetricBundleV1(**metrics_data)
            status_badge = metrics.status_badge
            reasons = metrics.reasons
        except (json.JSONDecodeError, ValueError):
            pass

    return RunDetail(
        run_id=run.run_id,
        experiment_id=run.experiment_id,
        item_id=run.item_id,
        variant_key=run.variant_key,
        spec_hash=run.spec_hash,
        status=run.status,
        output_canon_uri=run.output_canon_uri,
        output_sha256=run.output_sha256,
        metrics=metrics,
        status_badge=status_badge,
        reasons=reasons,
    )


@router.get("/experiments/{experiment_id}", response_model=ExperimentOverview)
def get_experiment(
    experiment_id: str,
    session: DbSession = Depends(get_db_session),
) -> ExperimentOverview:
    """Get experiment overview.

    Args:
        experiment_id: Experiment ID to fetch.
        session: Database session (injected).

    Returns:
        ExperimentOverview with all experiment data.

    Raises:
        HTTPException: 404 if experiment not found.
    """
    # Get experiment via repository
    experiment = repo.get_experiment(session, experiment_id)

    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Get generation spec via repository
    spec = repo.get_generation_spec(session, experiment.generation_spec_id)

    if spec is None:
        raise HTTPException(status_code=404, detail="Generation spec not found")

    # Get runs via repository
    runs = repo.get_runs_for_experiment(session, experiment_id)

    # Get dataset item from first run via repository
    dataset_item = None
    if runs:
        dataset_item = repo.get_dataset_item(session, runs[0].item_id)

    if dataset_item is None and runs:
        raise HTTPException(status_code=404, detail="Dataset item not found")

    # Build response
    spec_detail = GenerationSpecDetail(
        generation_spec_id=spec.generation_spec_id,
        provider=spec.provider,
        model=spec.model,
        model_version=spec.model_version,
        prompt_template=spec.prompt_template,
        params=json.loads(spec.params_json) if spec.params_json else None,
    )

    item_detail = (
        DatasetItemDetail(
            item_id=dataset_item.item_id if dataset_item else "",
            subject_id=dataset_item.subject_id if dataset_item else "",
            source_video_uri=dataset_item.source_video_uri if dataset_item else "",
            audio_uri=dataset_item.audio_uri if dataset_item else "",
            ref_image_uri=dataset_item.ref_image_uri if dataset_item else None,
        )
        if dataset_item
        else DatasetItemDetail(
            item_id="",
            subject_id="",
            source_video_uri="",
            audio_uri="",
            ref_image_uri=None,
        )
    )

    run_details = [_build_run_detail(session, run) for run in runs]

    return ExperimentOverview(
        experiment_id=experiment.experiment_id,
        status=experiment.status,
        generation_spec=spec_detail,
        dataset_item=item_detail,
        runs=run_details,
        human_summary=None,  # Will be implemented in PR12
    )
