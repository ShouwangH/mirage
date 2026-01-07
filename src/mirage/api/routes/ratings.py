"""Ratings API endpoint.

POST /api/ratings - Submit human rating
GET /api/experiments/{experiment_id}/summary - Get human evaluation summary
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from mirage.aggregation.summary import summarize_experiment
from mirage.api.app import get_db_session
from mirage.db import repo
from mirage.db.repo import DbSession
from mirage.eval.ratings import RatingInput, submit_rating
from mirage.models.types import HumanSummary, RatingSubmission

router = APIRouter()


class RatingCreatedResponse(BaseModel):
    """Response for rating submission."""

    rating_id: str
    task_id: str


@router.post("/ratings", response_model=RatingCreatedResponse, status_code=201)
def create_rating(
    rating: RatingSubmission,
    session: DbSession = Depends(get_db_session),
) -> RatingCreatedResponse:
    """Submit a human rating for a task.

    Args:
        rating: Rating submission data.
        session: Database session (injected).

    Returns:
        RatingCreatedResponse with rating_id.

    Raises:
        HTTPException: 404 if task not found.
    """
    # Verify task exists via repository
    task = repo.get_task(session, rating.task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    # Build typed input for domain layer
    rating_input = RatingInput(
        task_id=rating.task_id,
        rater_id=rating.rater_id,
        choice_realism=rating.choice_realism,
        choice_lipsync=rating.choice_lipsync,
        choice_targetmatch=rating.choice_targetmatch,
        notes=rating.notes,
    )

    try:
        result = submit_rating(session=session, rating_input=rating_input)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return RatingCreatedResponse(
        rating_id=result.rating_id,
        task_id=result.task_id,
    )


@router.get("/experiments/{experiment_id}/summary", response_model=HumanSummary)
def get_experiment_summary(
    experiment_id: str,
    session: DbSession = Depends(get_db_session),
) -> HumanSummary:
    """Get human evaluation summary for an experiment.

    Args:
        experiment_id: Experiment to summarize.
        session: Database session (injected).

    Returns:
        HumanSummary with win rates and recommended pick.

    Raises:
        HTTPException: 404 if experiment not found.
    """
    # Verify experiment exists via repository
    experiment = repo.get_experiment(session, experiment_id)

    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return summarize_experiment(session, experiment_id)
