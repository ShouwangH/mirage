"""Rating submission for human evaluation.

Handles rating storage and task status updates.
Domain logic is pure - database operations go through repo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from mirage.db import repo
from mirage.db.schema import HumanRating

Choice = Literal["left", "right", "tie", "skip"]


@dataclass
class RatingInput:
    """Input for rating submission."""

    task_id: str
    rater_id: str
    choice_realism: Choice
    choice_lipsync: Choice
    choice_targetmatch: Choice | None = None
    notes: str | None = None


@dataclass
class RatingResult:
    """Result of rating submission."""

    rating_id: str
    task_id: str
    success: bool


def submit_rating(
    session: Session,
    rating_input: RatingInput,
) -> RatingResult:
    """Submit a rating for a task.

    Creates a new rating record and updates task status to 'done'.

    Args:
        session: Database session.
        rating_input: Rating data.

    Returns:
        RatingResult with rating ID and success status.

    Raises:
        ValueError: If task not found.
    """
    # Verify task exists via repository
    task = repo.get_task(session, rating_input.task_id)
    if task is None:
        raise ValueError(f"Task not found: {rating_input.task_id}")

    # Create rating entity
    rating = _create_rating_entity(rating_input)

    # Persist via repository
    repo.create_rating(session, rating)
    repo.update_task_status(session, rating_input.task_id, "done")
    repo.commit(session)

    return RatingResult(
        rating_id=rating.rating_id,
        task_id=rating_input.task_id,
        success=True,
    )


def _create_rating_entity(rating_input: RatingInput) -> HumanRating:
    """Create rating entity from input.

    Pure function - no database access.

    Args:
        rating_input: Rating input data.

    Returns:
        HumanRating entity ready for insertion.
    """
    return HumanRating(
        rating_id=str(uuid.uuid4()),
        task_id=rating_input.task_id,
        rater_id=rating_input.rater_id,
        choice_realism=rating_input.choice_realism,
        choice_lipsync=rating_input.choice_lipsync,
        choice_targetmatch=rating_input.choice_targetmatch,
        notes=rating_input.notes,
    )
