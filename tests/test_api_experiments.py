"""Tests for experiments API endpoint.

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
    MetricResult,
    Run,
)


def create_test_app_and_client():
    """Create app with test database and return (client, engine)."""
    from mirage.api.app import create_app, get_db_session

    # Create in-memory database with StaticPool to share connection
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


def setup_test_data(engine) -> str:
    """Set up test database with complete experiment data."""
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
            spec_hash="abc123",
            status="succeeded",
            output_canon_uri="file:///output1.mp4",
            output_sha256="sha256_1",
        )
        run2 = Run(
            run_id="run-002",
            experiment_id="exp-001",
            item_id="item-001",
            variant_key="variant-b",
            spec_hash="def456",
            status="queued",
        )
        db_session.add(run1)
        db_session.add(run2)

        db_session.commit()
    return "exp-001"


class TestGetExperimentEndpoint:
    """Test GET /api/experiments/{experiment_id}."""

    def test_returns_200_for_existing_experiment(self):
        """Returns 200 OK for existing experiment."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        response = client.get(f"/api/experiments/{experiment_id}")
        assert response.status_code == 200

    def test_returns_404_for_nonexistent_experiment(self):
        """Returns 404 for nonexistent experiment."""
        client, _ = create_test_app_and_client()
        response = client.get("/api/experiments/nonexistent-id")
        assert response.status_code == 404

    def test_returns_experiment_overview_shape(self):
        """Response matches ExperimentOverview schema."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        response = client.get(f"/api/experiments/{experiment_id}")
        data = response.json()

        # Required top-level fields
        assert "experiment_id" in data
        assert "status" in data
        assert "generation_spec" in data
        assert "dataset_item" in data
        assert "runs" in data
        assert "human_summary" in data

    def test_returns_correct_experiment_id(self):
        """Response contains correct experiment_id."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        response = client.get(f"/api/experiments/{experiment_id}")
        data = response.json()
        assert data["experiment_id"] == experiment_id

    def test_returns_experiment_status(self):
        """Response contains experiment status."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        response = client.get(f"/api/experiments/{experiment_id}")
        data = response.json()
        assert data["status"] in ("draft", "running", "complete")

    def test_returns_generation_spec_details(self):
        """Response contains generation spec details."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        response = client.get(f"/api/experiments/{experiment_id}")
        data = response.json()
        spec = data["generation_spec"]

        assert "generation_spec_id" in spec
        assert "provider" in spec
        assert "model" in spec
        assert spec["provider"] == "mock"
        assert spec["model"] == "test-model"

    def test_returns_dataset_item_details(self):
        """Response contains dataset item details."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        response = client.get(f"/api/experiments/{experiment_id}")
        data = response.json()
        item = data["dataset_item"]

        assert "item_id" in item
        assert "subject_id" in item
        assert "source_video_uri" in item
        assert "audio_uri" in item
        assert item["item_id"] == "item-001"

    def test_returns_runs_list(self):
        """Response contains list of runs."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        response = client.get(f"/api/experiments/{experiment_id}")
        data = response.json()

        assert isinstance(data["runs"], list)
        assert len(data["runs"]) == 2

    def test_run_contains_required_fields(self):
        """Each run in response contains required fields."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        response = client.get(f"/api/experiments/{experiment_id}")
        data = response.json()

        for run in data["runs"]:
            assert "run_id" in run
            assert "experiment_id" in run
            assert "item_id" in run
            assert "variant_key" in run
            assert "spec_hash" in run
            assert "status" in run

    def test_human_summary_is_null_when_no_ratings(self):
        """human_summary is null when no ratings exist."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        response = client.get(f"/api/experiments/{experiment_id}")
        data = response.json()
        assert data["human_summary"] is None


class TestExperimentWithMetrics:
    """Test experiment response with metric data."""

    def test_run_includes_metrics_when_available(self):
        """Run includes metrics when MetricResult exists."""
        client, engine = create_test_app_and_client()
        experiment_id = setup_test_data(engine)

        # Add metric result
        with Session(engine) as session:
            metric_data = {
                "decode_ok": True,
                "video_duration_ms": 5000,
                "audio_duration_ms": 5000,
                "av_duration_delta_ms": 0,
                "fps": 30.0,
                "frame_count": 150,
                "scene_cut_count": 0,
                "freeze_frame_ratio": 0.0,
                "flicker_score": 1.0,
                "blur_score": 100.0,
                "frame_diff_spike_count": 0,
                "face_present_ratio": 0.95,
                "face_bbox_jitter": 0.01,
                "landmark_jitter": 0.01,
                "mouth_open_energy": 0.1,
                "mouth_audio_corr": 0.5,
                "blink_count": 3,
                "blink_rate_hz": 0.6,
                "lse_d": None,
                "lse_c": None,
                "status_badge": "pass",
                "reasons": [],
            }
            result = MetricResult(
                metric_result_id="metric-001",
                run_id="run-001",
                metric_name="MetricBundleV1",
                metric_version="1",
                value_json=json.dumps(metric_data),
                status="computed",
            )
            session.add(result)
            session.commit()

        response = client.get(f"/api/experiments/{experiment_id}")
        data = response.json()

        # Find run-001
        run = next(r for r in data["runs"] if r["run_id"] == "run-001")
        assert run["metrics"] is not None
        assert run["metrics"]["decode_ok"] is True
        assert run["status_badge"] == "pass"


class TestAPIHealthCheck:
    """Test API health check endpoint."""

    def test_health_endpoint_returns_200(self):
        """Health endpoint returns 200 OK."""
        client, _ = create_test_app_and_client()
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self):
        """Health endpoint returns ok status."""
        client, _ = create_test_app_and_client()
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"
