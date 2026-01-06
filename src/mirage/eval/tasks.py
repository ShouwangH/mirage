"""Pairwise task generation for human evaluation.

Creates pairwise comparison tasks from experiment runs with
randomization to prevent left/right bias.

Domain logic is pure - database operations go through repo.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from itertools import combinations

from sqlalchemy.orm import Session

from mirage.db import repo
from mirage.db.schema import HumanTask


@dataclass
class TaskCreationResult:
    """Result of task creation operation."""

    created_count: int
    task_ids: list[str]


def generate_pairwise_tasks(
    session: Session,
    experiment_id: str,
) -> TaskCreationResult:
    """Generate pairwise comparison tasks for an experiment.

    Creates tasks for all unique pairs of succeeded runs in the experiment.
    Each task randomly assigns left/right presentation to prevent bias.

    Args:
        session: Database session.
        experiment_id: Experiment to generate tasks for.

    Returns:
        TaskCreationResult with count and IDs of created tasks.
    """
    # Get succeeded run IDs via repository
    run_ids = repo.get_succeeded_run_ids_for_experiment(session, experiment_id)

    if len(run_ids) < 2:
        return TaskCreationResult(created_count=0, task_ids=[])

    # Get existing pairs to avoid duplicates
    existing_pairs = repo.get_existing_task_pairs(session, experiment_id)

    # Generate tasks for all unique pairs using run_id (not variant_key)
    created_task_ids: list[str] = []

    for run_id_a, run_id_b in combinations(run_ids, 2):
        # Check if pair already exists (order-independent)
        pair = tuple(sorted([run_id_a, run_id_b]))
        if pair in existing_pairs:
            continue

        # Create task with randomized presentation
        task = _create_pairwise_task(
            experiment_id=experiment_id,
            left_run_id=run_id_a,
            right_run_id=run_id_b,
        )
        repo.create_task(session, task)
        created_task_ids.append(task.task_id)

    if created_task_ids:
        repo.commit(session)

    return TaskCreationResult(
        created_count=len(created_task_ids),
        task_ids=created_task_ids,
    )


def _create_pairwise_task(
    experiment_id: str,
    left_run_id: str,
    right_run_id: str,
) -> HumanTask:
    """Create a pairwise task with randomized presentation.

    Pure function - no database access.

    Args:
        experiment_id: Experiment ID.
        left_run_id: First run to compare.
        right_run_id: Second run to compare.

    Returns:
        HumanTask ready for insertion.
    """
    # Randomly decide if we flip the presentation
    flip = secrets.randbelow(2) == 1

    if flip:
        presented_left = right_run_id
        presented_right = left_run_id
    else:
        presented_left = left_run_id
        presented_right = right_run_id

    return HumanTask(
        task_id=str(uuid.uuid4()),
        experiment_id=experiment_id,
        task_type="pairwise",
        left_run_id=left_run_id,
        right_run_id=right_run_id,
        presented_left_run_id=presented_left,
        presented_right_run_id=presented_right,
        flip=flip,
        status="open",
    )


def get_next_open_task(
    session: Session,
    experiment_id: str,
) -> HumanTask | None:
    """Get the next open task for an experiment.

    Args:
        session: Database session.
        experiment_id: Experiment to get task for.

    Returns:
        Next open HumanTask or None if no tasks available.
    """
    return repo.get_open_task_for_experiment(session, experiment_id)
