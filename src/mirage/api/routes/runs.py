"""Runs API endpoint.

GET /api/runs/{run_id} - Get run detail
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from mirage.api.app import get_db_session
from mirage.db import repo
from mirage.db.repo import DbSession
from mirage.models.domain import RunEntity
from mirage.models.types import MetricBundleV1, RunDetail

router = APIRouter()


def _build_run_detail(session: DbSession, run: RunEntity) -> RunDetail:
    """Build RunDetail from RunEntity.

    Args:
        session: Database session.
        run: Run entity.

    Returns:
        RunDetail model.
    """
    metrics = None
    status_badge = None
    reasons: list[str] = []

    # Get metrics via repository
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


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(
    run_id: str,
    session: DbSession = Depends(get_db_session),
) -> RunDetail:
    """Get run detail.

    Args:
        run_id: Run ID to fetch.
        session: Database session (injected).

    Returns:
        RunDetail with run data and metrics.

    Raises:
        HTTPException: 404 if run not found.
    """
    # Get run via repository
    run = repo.get_run(session, run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return _build_run_detail(session, run)
