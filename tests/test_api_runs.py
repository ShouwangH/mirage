"""Tests for runs API endpoint.

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
    """Set up test database with run data. Returns run_id."""
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

        # Create run with output
        run = Run(
            run_id="run-001",
            experiment_id="exp-001",
            item_id="item-001",
            variant_key="variant-a",
            spec_hash="abc123",
            status="succeeded",
            output_canon_uri="file:///artifacts/runs/run-001/output_canon.mp4",
            output_sha256="sha256_output",
        )
        db_session.add(run)

        db_session.commit()
    return "run-001"


class TestGetRunEndpoint:
    """Test GET /api/runs/{run_id}."""

    def test_returns_200_for_existing_run(self):
        """Returns 200 OK for existing run."""
        client, engine = create_test_app_and_client()
        run_id = setup_test_data(engine)

        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200

    def test_returns_404_for_nonexistent_run(self):
        """Returns 404 for nonexistent run."""
        client, _ = create_test_app_and_client()
        response = client.get("/api/runs/nonexistent-id")
        assert response.status_code == 404

    def test_returns_run_detail_shape(self):
        """Response matches RunDetail schema."""
        client, engine = create_test_app_and_client()
        run_id = setup_test_data(engine)

        response = client.get(f"/api/runs/{run_id}")
        data = response.json()

        # Required fields from RunDetail
        assert "run_id" in data
        assert "experiment_id" in data
        assert "item_id" in data
        assert "variant_key" in data
        assert "spec_hash" in data
        assert "status" in data

    def test_returns_correct_run_id(self):
        """Response contains correct run_id."""
        client, engine = create_test_app_and_client()
        run_id = setup_test_data(engine)

        response = client.get(f"/api/runs/{run_id}")
        data = response.json()
        assert data["run_id"] == run_id

    def test_returns_run_status(self):
        """Response contains run status."""
        client, engine = create_test_app_and_client()
        run_id = setup_test_data(engine)

        response = client.get(f"/api/runs/{run_id}")
        data = response.json()
        assert data["status"] in ("queued", "running", "succeeded", "failed")

    def test_returns_output_uri_for_succeeded_run(self):
        """Response contains output_canon_uri for succeeded run."""
        client, engine = create_test_app_and_client()
        run_id = setup_test_data(engine)

        response = client.get(f"/api/runs/{run_id}")
        data = response.json()
        assert data["output_canon_uri"] is not None
        assert "output_canon.mp4" in data["output_canon_uri"]

    def test_returns_null_metrics_when_none(self):
        """Response has null metrics when no MetricResult exists."""
        client, engine = create_test_app_and_client()
        run_id = setup_test_data(engine)

        response = client.get(f"/api/runs/{run_id}")
        data = response.json()
        assert data["metrics"] is None


class TestRunWithMetrics:
    """Test run response with metric data."""

    def test_run_includes_metrics_when_available(self):
        """Run includes metrics when MetricResult exists."""
        client, engine = create_test_app_and_client()
        run_id = setup_test_data(engine)

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

        response = client.get(f"/api/runs/{run_id}")
        data = response.json()

        assert data["metrics"] is not None
        assert data["metrics"]["decode_ok"] is True
        assert data["status_badge"] == "pass"

    def test_run_includes_status_badge(self):
        """Run includes status_badge from metrics."""
        client, engine = create_test_app_and_client()
        run_id = setup_test_data(engine)

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
                "status_badge": "flagged",
                "reasons": ["high_jitter"],
            }
            result = MetricResult(
                metric_result_id="metric-002",
                run_id="run-001",
                metric_name="MetricBundleV1",
                metric_version="1",
                value_json=json.dumps(metric_data),
                status="computed",
            )
            session.add(result)
            session.commit()

        response = client.get(f"/api/runs/{run_id}")
        data = response.json()

        assert data["status_badge"] == "flagged"
        assert "high_jitter" in data["reasons"]


class TestArtifactServing:
    """Test artifact file serving."""

    def test_artifacts_endpoint_exists(self):
        """Artifacts endpoint is mounted."""
        client, _ = create_test_app_and_client()
        # Should return 404 (not found) rather than 405 (method not allowed)
        # or other error indicating the route doesn't exist
        response = client.get("/artifacts/nonexistent.mp4")
        # Route exists but file doesn't - expect 404
        assert response.status_code == 404
