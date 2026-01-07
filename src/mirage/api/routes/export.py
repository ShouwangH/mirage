"""Export API endpoint.

GET /api/experiments/{experiment_id}/export - Export experiment results as JSON
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mirage.aggregation.summary import summarize_experiment
from mirage.api.app import get_db_session
from mirage.db import repo
from mirage.db.repo import DbSession
from mirage.models.domain import RunEntity
from mirage.models.types import MetricBundleV1

router = APIRouter()


def _get_metrics_for_run(session: DbSession, run: RunEntity) -> MetricBundleV1 | None:
    """Get metrics for a run from metric_results table."""
    metric_result = repo.get_metric_result(session, run.run_id)
    if metric_result and metric_result.value_json:
        try:
            metrics_data = json.loads(metric_result.value_json)
            return MetricBundleV1(**metrics_data)
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _build_exported_runs(
    session: DbSession, runs: list[RunEntity]
) -> list["ExportedRun"]:
    """Build exported runs with metrics."""
    result = []
    for run in runs:
        metrics = _get_metrics_for_run(session, run)
        result.append(
            ExportedRun(
                run_id=run.run_id,
                variant_key=run.variant_key,
                status=run.status,
                output_sha256=run.output_sha256,
                metrics=metrics,
                status_badge=metrics.status_badge if metrics else None,
                reasons=metrics.reasons if metrics else [],
            )
        )
    return result


class ExportedRun(BaseModel):
    """Exported run data."""

    run_id: str
    variant_key: str
    status: str
    output_sha256: str | None
    metrics: MetricBundleV1 | None
    status_badge: str | None
    reasons: list[str]


class ExportedExperiment(BaseModel):
    """Full experiment export."""

    experiment_id: str
    status: str
    generation_spec: dict
    dataset_item: dict
    runs: list[ExportedRun]
    human_summary: dict | None
    export_version: str = "1.0"


@router.get("/experiments/{experiment_id}/export")
def export_experiment(
    experiment_id: str,
    session: DbSession = Depends(get_db_session),
) -> JSONResponse:
    """Export experiment results as downloadable JSON.

    Args:
        experiment_id: Experiment to export.
        session: Database session (injected).

    Returns:
        JSON response with Content-Disposition header for download.

    Raises:
        HTTPException: 404 if experiment not found.
    """
    # Get experiment via repository
    experiment = repo.get_experiment(session, experiment_id)

    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Get generation spec
    gen_spec = repo.get_generation_spec(session, experiment.generation_spec_id)

    # Get all runs
    runs = repo.get_runs_for_experiment(session, experiment_id)

    # Get dataset item from first run
    dataset_item = None
    if runs:
        dataset_item = repo.get_dataset_item(session, runs[0].item_id)

    # Get human summary
    try:
        human_summary = summarize_experiment(session, experiment_id)
        summary_dict = {
            "win_rates": human_summary.win_rates,
            "recommended_pick": human_summary.recommended_pick,
            "total_comparisons": human_summary.total_comparisons,
        }
    except Exception:
        summary_dict = None

    # Build export data
    export_data = ExportedExperiment(
        experiment_id=experiment.experiment_id,
        status=experiment.status,
        generation_spec={
            "generation_spec_id": gen_spec.generation_spec_id if gen_spec else None,
            "provider": gen_spec.provider if gen_spec else None,
            "model": gen_spec.model if gen_spec else None,
            "model_version": gen_spec.model_version if gen_spec else None,
            "prompt_template": gen_spec.prompt_template if gen_spec else None,
            "params": json.loads(gen_spec.params_json) if gen_spec and gen_spec.params_json else None,
        },
        dataset_item={
            "item_id": dataset_item.item_id if dataset_item else None,
            "subject_id": dataset_item.subject_id if dataset_item else None,
            "source_video_uri": dataset_item.source_video_uri if dataset_item else None,
            "audio_uri": dataset_item.audio_uri if dataset_item else None,
            "ref_image_uri": dataset_item.ref_image_uri if dataset_item else None,
        },
        runs=_build_exported_runs(session, runs),
        human_summary=summary_dict,
    )

    # Return as downloadable JSON
    return JSONResponse(
        content=export_data.model_dump(),
        headers={
            "Content-Disposition": f'attachment; filename="{experiment_id}_export.json"'
        },
    )
