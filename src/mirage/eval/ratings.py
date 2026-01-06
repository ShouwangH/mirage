"""Rating submission for human evaluation.

Handles rating storage and task status updates.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from mirage.db.schema import HumanRating, HumanTask


def submit_rating(
    session: Session,
    task_id: str,
    rater_id: str,
    choice_realism: str,
    choice_lipsync: str,
    choice_targetmatch: str | None,
    notes: str | None,
) -> HumanRating:
    """Submit a rating for a task.

    Creates a new rating record and updates task status to 'done'.

    Args:
        session: Database session.
        task_id: Task being rated.
        rater_id: Rater identifier.
        choice_realism: Realism choice (left/right/tie/skip).
        choice_lipsync: Lipsync choice (left/right/tie/skip).
        choice_targetmatch: Target match choice (optional).
        notes: Optional notes.

    Returns:
        Created HumanRating record.

    Raises:
        ValueError: If task not found.
    """
    # Verify task exists
    task = session.query(HumanTask).filter(HumanTask.task_id == task_id).first()
    if task is None:
        raise ValueError(f"Task not found: {task_id}")

    # Create rating
    rating = HumanRating(
        rating_id=str(uuid.uuid4()),
        task_id=task_id,
        rater_id=rater_id,
        choice_realism=choice_realism,
        choice_lipsync=choice_lipsync,
        choice_targetmatch=choice_targetmatch,
        notes=notes,
    )
    session.add(rating)

    # Update task status
    task.status = "done"

    session.commit()

    return rating
