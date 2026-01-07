"""Human evaluation summary aggregation.

Computes win rates and recommended pick from human ratings.
Domain logic is pure - database operations go through repo.
"""

from __future__ import annotations

from dataclasses import dataclass

from mirage.db import repo
from mirage.db.repo import DbSession
from mirage.models.domain import RatingEntity, TaskEntity
from mirage.models.types import HumanSummary


@dataclass
class TaskRatingPair:
    """Internal pairing of task and its ratings for computation."""

    task: TaskEntity
    ratings: list[RatingEntity]


def summarize_experiment(
    session: DbSession,
    experiment_id: str,
) -> HumanSummary:
    """Compute human evaluation summary for an experiment.

    Calculates win rates based on pairwise comparison ratings.
    A run "wins" a comparison when chosen for realism OR lipsync.

    Args:
        session: Database session.
        experiment_id: Experiment to summarize.

    Returns:
        HumanSummary with win rates (by run_id) and recommended pick.
    """
    # Get completed tasks via repository
    tasks = repo.get_done_tasks_for_experiment(session, experiment_id)

    if not tasks:
        return HumanSummary(
            win_rates={},
            recommended_pick=None,
            total_comparisons=0,
        )

    # Get all run IDs for this experiment to initialize win tracking
    run_ids = repo.get_succeeded_run_ids_for_experiment(session, experiment_id)

    # Get all ratings in one query via repository
    task_ids = [t.task_id for t in tasks]
    all_ratings = repo.get_ratings_for_tasks(session, task_ids)

    # Group ratings by task_id for efficient lookup
    ratings_by_task: dict[str, list[RatingEntity]] = {}
    for rating in all_ratings:
        if rating.task_id not in ratings_by_task:
            ratings_by_task[rating.task_id] = []
        ratings_by_task[rating.task_id].append(rating)

    # Build task-rating pairs for pure computation
    task_rating_pairs = [
        TaskRatingPair(task=task, ratings=ratings_by_task.get(task.task_id, []))
        for task in tasks
    ]

    # Compute win rates using pure domain logic
    return _compute_win_rates(run_ids, task_rating_pairs)


def _compute_win_rates(
    run_ids: list[str],
    task_rating_pairs: list[TaskRatingPair],
) -> HumanSummary:
    """Compute win rates from task-rating pairs.

    Pure function - no database access.

    Args:
        run_ids: All run IDs to include in results.
        task_rating_pairs: Tasks paired with their ratings.

    Returns:
        HumanSummary with computed win rates.
    """
    # Initialize all runs with 0 wins
    wins: dict[str, float] = {run_id: 0.0 for run_id in run_ids}
    total_comparisons = 0

    for pair in task_rating_pairs:
        task = pair.task

        for rating in pair.ratings:
            total_comparisons += 1

            # Use canonical run IDs directly
            left_run_id = task.left_run_id
            right_run_id = task.right_run_id

            # Count wins based on choices
            # "left" in rating means the presented left won
            # Need to account for flip to map back to canonical run IDs
            for choice in [rating.choice_realism, rating.choice_lipsync]:
                if choice == "left":
                    # Presented left won
                    if task.flip:
                        # When flipped, right_run was presented as left
                        wins[right_run_id] += 0.5
                    else:
                        wins[left_run_id] += 0.5
                elif choice == "right":
                    # Presented right won
                    if task.flip:
                        # When flipped, left_run was presented as right
                        wins[left_run_id] += 0.5
                    else:
                        wins[right_run_id] += 0.5
                elif choice == "tie":
                    # Both get half credit
                    wins[left_run_id] += 0.25
                    wins[right_run_id] += 0.25
                # "skip" gives no credit

    # Calculate win rates
    # Total possible wins = 2 choices * total_comparisons
    total_possible = 2 * total_comparisons if total_comparisons > 0 else 1
    win_rates = {run_id: score / total_possible for run_id, score in wins.items()}

    # Determine recommended pick (highest win rate)
    recommended_pick = None
    if win_rates:
        recommended_pick = max(win_rates, key=lambda r: win_rates[r])

    return HumanSummary(
        win_rates=win_rates,
        recommended_pick=recommended_pick,
        total_comparisons=total_comparisons,
    )
