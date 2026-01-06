"""Pairwise task generation for human evaluation.

Creates pairwise comparison tasks from experiment runs with
randomization to prevent left/right bias.
"""

from __future__ import annotations

import secrets
import uuid
from itertools import combinations

from sqlalchemy.orm import Session

from mirage.db.schema import HumanTask, Run


def generate_pairwise_tasks(
    session: Session,
    experiment_id: str,
) -> list[HumanTask]:
    """Generate pairwise comparison tasks for an experiment.

    Creates tasks for all unique pairs of succeeded runs in the experiment.
    Each task randomly assigns left/right presentation to prevent bias.

    Args:
        session: Database session.
        experiment_id: Experiment to generate tasks for.

    Returns:
        List of created HumanTask objects.
    """
    # Get all succeeded runs for this experiment
    runs = (
        session.query(Run)
        .filter(
            Run.experiment_id == experiment_id,
            Run.status == "succeeded",
        )
        .all()
    )

    if len(runs) < 2:
        return []

    # Get existing tasks to avoid duplicates
    existing_tasks = session.query(HumanTask).filter(HumanTask.experiment_id == experiment_id).all()

    # Build set of existing pairs (order-independent)
    existing_pairs = set()
    for task in existing_tasks:
        pair = tuple(sorted([task.left_run_id, task.right_run_id]))
        existing_pairs.add(pair)

    # Generate tasks for all unique pairs
    created_tasks = []
    for run_a, run_b in combinations(runs, 2):
        # Check if pair already exists
        pair = tuple(sorted([run_a.run_id, run_b.run_id]))
        if pair in existing_pairs:
            continue

        # Randomly decide if we flip the presentation
        flip = secrets.randbelow(2) == 1

        if flip:
            presented_left = run_b.run_id
            presented_right = run_a.run_id
        else:
            presented_left = run_a.run_id
            presented_right = run_b.run_id

        task = HumanTask(
            task_id=str(uuid.uuid4()),
            experiment_id=experiment_id,
            task_type="pairwise",
            left_run_id=run_a.run_id,
            right_run_id=run_b.run_id,
            presented_left_run_id=presented_left,
            presented_right_run_id=presented_right,
            flip=flip,
            status="open",
        )
        session.add(task)
        created_tasks.append(task)

    if created_tasks:
        session.commit()

    return created_tasks


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
    return (
        session.query(HumanTask)
        .filter(
            HumanTask.experiment_id == experiment_id,
            HumanTask.status == "open",
        )
        .first()
    )
