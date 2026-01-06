"""Human evaluation summary aggregation.

Computes win rates and recommended pick from human ratings.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from mirage.db.schema import HumanRating, HumanTask, Run
from mirage.models.types import HumanSummary


def summarize_experiment(
    session: Session,
    experiment_id: str,
) -> HumanSummary:
    """Compute human evaluation summary for an experiment.

    Calculates win rates based on pairwise comparison ratings.
    A variant "wins" a comparison when chosen for realism OR lipsync.

    Args:
        session: Database session.
        experiment_id: Experiment to summarize.

    Returns:
        HumanSummary with win rates and recommended pick.
    """
    # Get all tasks for this experiment
    tasks = (
        session.query(HumanTask)
        .filter(
            HumanTask.experiment_id == experiment_id,
            HumanTask.status == "done",
        )
        .all()
    )

    if not tasks:
        return HumanSummary(
            win_rates={},
            recommended_pick=None,
            total_comparisons=0,
        )

    # Get all runs to map run_id -> variant_key
    runs = session.query(Run).filter(Run.experiment_id == experiment_id).all()
    run_to_variant = {run.run_id: run.variant_key for run in runs}

    # Initialize all variants with 0 wins
    wins: dict[str, float] = {run.variant_key: 0.0 for run in runs}
    total_comparisons = 0

    for task in tasks:
        # Get ratings for this task
        ratings = session.query(HumanRating).filter(HumanRating.task_id == task.task_id).all()

        for rating in ratings:
            total_comparisons += 1

            # Map presented choices back to canonical run IDs
            # If flip=True, presented_left was actually right_run_id
            left_variant = run_to_variant.get(task.left_run_id, task.left_run_id)
            right_variant = run_to_variant.get(task.right_run_id, task.right_run_id)

            # Count wins based on choices
            # "left" in rating means the presented left won
            # Need to account for flip
            for choice in [rating.choice_realism, rating.choice_lipsync]:
                if choice == "left":
                    # Presented left won
                    if task.flip:
                        wins[right_variant] += 0.5  # right_run was presented as left
                    else:
                        wins[left_variant] += 0.5
                elif choice == "right":
                    # Presented right won
                    if task.flip:
                        wins[left_variant] += 0.5  # left_run was presented as right
                    else:
                        wins[right_variant] += 0.5
                elif choice == "tie":
                    # Both get half credit
                    wins[left_variant] += 0.25
                    wins[right_variant] += 0.25
                # "skip" gives no credit

    # Calculate win rates
    # Total possible wins = 2 choices * total_comparisons
    total_possible = 2 * total_comparisons if total_comparisons > 0 else 1
    win_rates = {variant: score / total_possible for variant, score in wins.items()}

    # Determine recommended pick (highest win rate)
    recommended_pick = None
    if win_rates:
        recommended_pick = max(win_rates, key=lambda v: win_rates[v])

    return HumanSummary(
        win_rates=win_rates,
        recommended_pick=recommended_pick,
        total_comparisons=total_comparisons,
    )
