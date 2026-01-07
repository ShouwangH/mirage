"""Tasks API endpoint.

POST /api/experiments/{experiment_id}/tasks - Create pairwise tasks
GET /api/tasks/{task_id} - Get task detail
GET /api/experiments/{experiment_id}/tasks/next - Get next open task
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from mirage.api.app import get_db_session
from mirage.db import repo
from mirage.db.repo import DbSession
from mirage.eval.tasks import generate_pairwise_tasks, get_next_open_task
from mirage.models.domain import TaskEntity
from mirage.models.types import TaskDetail

router = APIRouter()


class TasksCreatedResponse(BaseModel):
    """Response for task creation."""

    tasks_created: int
    experiment_id: str


def _task_to_detail(task: TaskEntity) -> TaskDetail:
    """Convert TaskEntity to TaskDetail."""
    return TaskDetail(
        task_id=task.task_id,
        experiment_id=task.experiment_id,
        left_run_id=task.left_run_id,
        right_run_id=task.right_run_id,
        presented_left_run_id=task.presented_left_run_id,
        presented_right_run_id=task.presented_right_run_id,
        flip=task.flip,
        status=task.status,
    )


@router.post(
    "/experiments/{experiment_id}/tasks",
    response_model=TasksCreatedResponse,
    status_code=201,
)
def create_tasks(
    experiment_id: str,
    session: DbSession = Depends(get_db_session),
) -> TasksCreatedResponse:
    """Create pairwise comparison tasks for an experiment.

    Args:
        experiment_id: Experiment to create tasks for.
        session: Database session (injected).

    Returns:
        TasksCreatedResponse with count of tasks created.

    Raises:
        HTTPException: 404 if experiment not found.
    """
    # Verify experiment exists via repository
    experiment = repo.get_experiment(session, experiment_id)

    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Generate tasks - returns TaskCreationResult
    result = generate_pairwise_tasks(session, experiment_id)

    return TasksCreatedResponse(
        tasks_created=result.created_count,
        experiment_id=experiment_id,
    )


@router.get("/tasks/{task_id}", response_model=TaskDetail)
def get_task(
    task_id: str,
    session: DbSession = Depends(get_db_session),
) -> TaskDetail:
    """Get task detail.

    Args:
        task_id: Task ID to fetch.
        session: Database session (injected).

    Returns:
        TaskDetail with task data.

    Raises:
        HTTPException: 404 if task not found.
    """
    # Get task via repository
    task = repo.get_task(session, task_id)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return _task_to_detail(task)


@router.get("/experiments/{experiment_id}/tasks/next", response_model=TaskDetail)
def get_next_task(
    experiment_id: str,
    session: DbSession = Depends(get_db_session),
) -> TaskDetail:
    """Get next open task for an experiment.

    Args:
        experiment_id: Experiment to get task for.
        session: Database session (injected).

    Returns:
        TaskDetail for next open task.

    Raises:
        HTTPException: 404 if no open tasks available.
    """
    task = get_next_open_task(session, experiment_id)

    if task is None:
        raise HTTPException(status_code=404, detail="No open tasks available")

    return _task_to_detail(task)
