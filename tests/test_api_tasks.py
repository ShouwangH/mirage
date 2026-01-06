"""Tests for tasks API endpoint.

TDD: Tests written first per IMPLEMENTATION_PLAN.md.
"""

import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from mirage.db.schema import (
    Base,
    DatasetItem,
    Experiment,
    GenerationSpec,
    HumanTask,
    Run,
)


def create_test_app_and_client():
    """Create app with test database and return (client, engine)."""
    from mirage.api.app import create_app, get_db_session

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    app = create_app()

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db
    client = TestClient(app)

    return client, engine


def setup_experiment_with_runs(engine, num_runs: int = 2) -> str:
    """Set up experiment with multiple runs. Returns experiment_id."""
    with Session(engine) as db_session:
        # Create dataset item
        item = DatasetItem(
            item_id="item-001",
            subject_id="subject-001",
            source_video_uri="file:///source.mp4",
            audio_uri="file:///audio.wav",
            ref_image_uri=None,
        )
        db_session.add(item)

        # Create generation spec
        spec = GenerationSpec(
            generation_spec_id="spec-001",
            provider="mock",
            model="test-model",
            model_version="1.0",
            prompt_template="Generate video",
            params_json=json.dumps({"quality": "high"}),
        )
        db_session.add(spec)

        # Create experiment
        exp = Experiment(
            experiment_id="exp-001",
            generation_spec_id="spec-001",
            status="running",
        )
        db_session.add(exp)

        # Create runs
        for i in range(num_runs):
            run = Run(
                run_id=f"run-{i + 1:03d}",
                experiment_id="exp-001",
                item_id="item-001",
                variant_key=f"variant-{chr(97 + i)}",  # variant-a, variant-b, etc.
                spec_hash=f"hash{i + 1}",
                status="succeeded",
                output_canon_uri=f"file:///output{i + 1}.mp4",
                output_sha256=f"sha256_{i + 1}",
            )
            db_session.add(run)

        db_session.commit()
    return "exp-001"


class TestCreateTasksEndpoint:
    """Test POST /api/experiments/{experiment_id}/tasks."""

    def test_returns_201_for_valid_experiment(self):
        """Returns 201 Created for valid experiment."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)

        response = client.post(f"/api/experiments/{experiment_id}/tasks")
        assert response.status_code == 201

    def test_returns_404_for_nonexistent_experiment(self):
        """Returns 404 for nonexistent experiment."""
        client, _ = create_test_app_and_client()
        response = client.post("/api/experiments/nonexistent/tasks")
        assert response.status_code == 404

    def test_creates_pairwise_tasks(self):
        """Creates pairwise tasks for experiment runs."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)

        response = client.post(f"/api/experiments/{experiment_id}/tasks")
        data = response.json()

        assert "tasks_created" in data
        assert data["tasks_created"] >= 1

    def test_returns_task_count(self):
        """Response includes count of tasks created."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=3)

        response = client.post(f"/api/experiments/{experiment_id}/tasks")
        data = response.json()

        # 3 runs = 3 pairs: (a,b), (a,c), (b,c)
        assert data["tasks_created"] == 3

    def test_records_flip_for_bias_prevention(self):
        """Tasks record flip flag for bias prevention."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)

        client.post(f"/api/experiments/{experiment_id}/tasks")

        # Check tasks in database
        with Session(engine) as session:
            tasks = session.query(HumanTask).all()
            assert len(tasks) >= 1
            # Each task should have flip recorded (True or False)
            for task in tasks:
                assert task.flip in (True, False)

    def test_presented_order_matches_flip(self):
        """presented_left/right_run_id matches flip flag."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)

        client.post(f"/api/experiments/{experiment_id}/tasks")

        with Session(engine) as session:
            tasks = session.query(HumanTask).all()
            for task in tasks:
                if task.flip:
                    # Flipped: presented is swapped
                    assert task.presented_left_run_id == task.right_run_id
                    assert task.presented_right_run_id == task.left_run_id
                else:
                    # Not flipped: presented matches original
                    assert task.presented_left_run_id == task.left_run_id
                    assert task.presented_right_run_id == task.right_run_id

    def test_idempotent_task_creation(self):
        """Calling endpoint twice doesn't duplicate tasks."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)

        response1 = client.post(f"/api/experiments/{experiment_id}/tasks")
        response2 = client.post(f"/api/experiments/{experiment_id}/tasks")

        # Second call should not create more tasks
        assert response2.json()["tasks_created"] == 0

        with Session(engine) as session:
            tasks = session.query(HumanTask).all()
            # Should still have same number of tasks
            assert len(tasks) == response1.json()["tasks_created"]


class TestGetTaskEndpoint:
    """Test GET /api/tasks/{task_id}."""

    def test_returns_200_for_existing_task(self):
        """Returns 200 OK for existing task."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)

        # Create tasks
        client.post(f"/api/experiments/{experiment_id}/tasks")

        # Get task ID from database
        with Session(engine) as session:
            task = session.query(HumanTask).first()
            task_id = task.task_id

        response = client.get(f"/api/tasks/{task_id}")
        assert response.status_code == 200

    def test_returns_404_for_nonexistent_task(self):
        """Returns 404 for nonexistent task."""
        client, _ = create_test_app_and_client()
        response = client.get("/api/tasks/nonexistent")
        assert response.status_code == 404

    def test_returns_task_detail_shape(self):
        """Response matches TaskDetail schema."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)

        client.post(f"/api/experiments/{experiment_id}/tasks")

        with Session(engine) as session:
            task = session.query(HumanTask).first()
            task_id = task.task_id

        response = client.get(f"/api/tasks/{task_id}")
        data = response.json()

        assert "task_id" in data
        assert "experiment_id" in data
        assert "left_run_id" in data
        assert "right_run_id" in data
        assert "presented_left_run_id" in data
        assert "presented_right_run_id" in data
        assert "flip" in data
        assert "status" in data


class TestGetNextTaskEndpoint:
    """Test GET /api/experiments/{experiment_id}/tasks/next."""

    def test_returns_200_when_task_available(self):
        """Returns 200 OK when open task available."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)

        client.post(f"/api/experiments/{experiment_id}/tasks")

        response = client.get(f"/api/experiments/{experiment_id}/tasks/next")
        assert response.status_code == 200

    def test_returns_404_when_no_tasks(self):
        """Returns 404 when no open tasks available."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)
        # Don't create tasks

        response = client.get(f"/api/experiments/{experiment_id}/tasks/next")
        assert response.status_code == 404

    def test_returns_task_detail(self):
        """Returns task detail for next available task."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_experiment_with_runs(engine, num_runs=2)

        client.post(f"/api/experiments/{experiment_id}/tasks")

        response = client.get(f"/api/experiments/{experiment_id}/tasks/next")
        data = response.json()

        assert "task_id" in data
        assert "status" in data
        assert data["status"] == "open"
