"""Tests for ratings API endpoint.

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
    HumanRating,
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


def setup_experiment_with_task(engine) -> tuple[str, str]:
    """Set up experiment with task. Returns (experiment_id, task_id)."""
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
        run1 = Run(
            run_id="run-001",
            experiment_id="exp-001",
            item_id="item-001",
            variant_key="variant-a",
            spec_hash="hash1",
            status="succeeded",
            output_canon_uri="file:///output1.mp4",
            output_sha256="sha256_1",
        )
        run2 = Run(
            run_id="run-002",
            experiment_id="exp-001",
            item_id="item-001",
            variant_key="variant-b",
            spec_hash="hash2",
            status="succeeded",
            output_canon_uri="file:///output2.mp4",
            output_sha256="sha256_2",
        )
        db_session.add(run1)
        db_session.add(run2)

        # Create task
        task = HumanTask(
            task_id="task-001",
            experiment_id="exp-001",
            task_type="pairwise",
            left_run_id="run-001",
            right_run_id="run-002",
            presented_left_run_id="run-001",
            presented_right_run_id="run-002",
            flip=False,
            status="open",
        )
        db_session.add(task)

        db_session.commit()
    return "exp-001", "task-001"


class TestSubmitRatingEndpoint:
    """Test POST /api/ratings."""

    def test_returns_201_for_valid_rating(self):
        """Returns 201 Created for valid rating submission."""
        client, engine = create_test_app_and_client()
        _, task_id = setup_experiment_with_task(engine)

        response = client.post(
            "/api/ratings",
            json={
                "task_id": task_id,
                "rater_id": "rater-001",
                "choice_realism": "left",
                "choice_lipsync": "right",
                "choice_targetmatch": None,
                "notes": None,
            },
        )
        assert response.status_code == 201

    def test_returns_404_for_nonexistent_task(self):
        """Returns 404 for nonexistent task."""
        client, _ = create_test_app_and_client()

        response = client.post(
            "/api/ratings",
            json={
                "task_id": "nonexistent",
                "rater_id": "rater-001",
                "choice_realism": "left",
                "choice_lipsync": "right",
                "choice_targetmatch": None,
                "notes": None,
            },
        )
        assert response.status_code == 404

    def test_creates_rating_record(self):
        """Creates rating record in database."""
        client, engine = create_test_app_and_client()
        _, task_id = setup_experiment_with_task(engine)

        client.post(
            "/api/ratings",
            json={
                "task_id": task_id,
                "rater_id": "rater-001",
                "choice_realism": "left",
                "choice_lipsync": "tie",
                "choice_targetmatch": "right",
                "notes": "Good quality",
            },
        )

        with Session(engine) as session:
            ratings = session.query(HumanRating).all()
            assert len(ratings) == 1
            assert ratings[0].task_id == task_id
            assert ratings[0].rater_id == "rater-001"
            assert ratings[0].choice_realism == "left"
            assert ratings[0].choice_lipsync == "tie"

    def test_updates_task_status_to_done(self):
        """Updates task status to 'done' after rating."""
        client, engine = create_test_app_and_client()
        _, task_id = setup_experiment_with_task(engine)

        client.post(
            "/api/ratings",
            json={
                "task_id": task_id,
                "rater_id": "rater-001",
                "choice_realism": "left",
                "choice_lipsync": "right",
                "choice_targetmatch": None,
                "notes": None,
            },
        )

        with Session(engine) as session:
            task = session.query(HumanTask).filter(HumanTask.task_id == task_id).first()
            assert task.status == "done"

    def test_append_only_ratings(self):
        """Multiple ratings can be submitted (append-only)."""
        client, engine = create_test_app_and_client()
        _, task_id = setup_experiment_with_task(engine)

        # Submit first rating
        client.post(
            "/api/ratings",
            json={
                "task_id": task_id,
                "rater_id": "rater-001",
                "choice_realism": "left",
                "choice_lipsync": "right",
                "choice_targetmatch": None,
                "notes": None,
            },
        )

        # Reset task status for second rating
        with Session(engine) as session:
            task = session.query(HumanTask).filter(HumanTask.task_id == task_id).first()
            task.status = "open"
            session.commit()

        # Submit second rating from different rater
        client.post(
            "/api/ratings",
            json={
                "task_id": task_id,
                "rater_id": "rater-002",
                "choice_realism": "right",
                "choice_lipsync": "left",
                "choice_targetmatch": None,
                "notes": None,
            },
        )

        with Session(engine) as session:
            ratings = session.query(HumanRating).all()
            assert len(ratings) == 2

    def test_returns_rating_id(self):
        """Response includes rating_id."""
        client, engine = create_test_app_and_client()
        _, task_id = setup_experiment_with_task(engine)

        response = client.post(
            "/api/ratings",
            json={
                "task_id": task_id,
                "rater_id": "rater-001",
                "choice_realism": "left",
                "choice_lipsync": "right",
                "choice_targetmatch": None,
                "notes": None,
            },
        )
        data = response.json()
        assert "rating_id" in data


class TestHumanSummaryEndpoint:
    """Test GET /api/experiments/{experiment_id}/summary."""

    def test_returns_200_for_experiment_with_ratings(self):
        """Returns 200 OK for experiment with ratings."""
        client, engine = create_test_app_and_client()
        experiment_id, task_id = setup_experiment_with_task(engine)

        # Submit a rating
        client.post(
            "/api/ratings",
            json={
                "task_id": task_id,
                "rater_id": "rater-001",
                "choice_realism": "left",
                "choice_lipsync": "left",
                "choice_targetmatch": None,
                "notes": None,
            },
        )

        response = client.get(f"/api/experiments/{experiment_id}/summary")
        assert response.status_code == 200

    def test_returns_404_for_nonexistent_experiment(self):
        """Returns 404 for nonexistent experiment."""
        client, _ = create_test_app_and_client()
        response = client.get("/api/experiments/nonexistent/summary")
        assert response.status_code == 404

    def test_returns_human_summary_shape(self):
        """Response matches HumanSummary schema."""
        client, engine = create_test_app_and_client()
        experiment_id, task_id = setup_experiment_with_task(engine)

        client.post(
            "/api/ratings",
            json={
                "task_id": task_id,
                "rater_id": "rater-001",
                "choice_realism": "left",
                "choice_lipsync": "left",
                "choice_targetmatch": None,
                "notes": None,
            },
        )

        response = client.get(f"/api/experiments/{experiment_id}/summary")
        data = response.json()

        assert "win_rates" in data
        assert "recommended_pick" in data
        assert "total_comparisons" in data

    def test_calculates_win_rates(self):
        """Calculates win rates from ratings."""
        client, engine = create_test_app_and_client()
        experiment_id, task_id = setup_experiment_with_task(engine)

        # Submit rating where left wins both
        client.post(
            "/api/ratings",
            json={
                "task_id": task_id,
                "rater_id": "rater-001",
                "choice_realism": "left",
                "choice_lipsync": "left",
                "choice_targetmatch": None,
                "notes": None,
            },
        )

        response = client.get(f"/api/experiments/{experiment_id}/summary")
        data = response.json()

        # Left (variant-a) should have higher win rate
        assert data["total_comparisons"] == 1
        assert "variant-a" in data["win_rates"]
        assert "variant-b" in data["win_rates"]

    def test_returns_null_for_no_ratings(self):
        """Returns null summary when no ratings exist."""
        client, engine = create_test_app_and_client()
        experiment_id, _ = setup_experiment_with_task(engine)

        response = client.get(f"/api/experiments/{experiment_id}/summary")
        # Should return empty/null summary
        data = response.json()
        assert data["total_comparisons"] == 0
