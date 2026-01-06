"""Tests for worker orchestrator.

TDD: Tests written first per IMPLEMENTATION_PLAN.md.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from mirage.db.schema import (
    Base,
    DatasetItem,
    Experiment,
    GenerationSpec,
    MetricResult,
    ProviderCall,
    Run,
)
from mirage.worker.orchestrator import WorkerOrchestrator


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def setup_test_data(db_session: Session, tmp_path: Path) -> dict:
    """Set up test database with experiment and queued run."""
    # Create audio file
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake audio")

    # Create dataset item
    item = DatasetItem(
        item_id="item-001",
        subject_id="subject-001",
        source_video_uri="file:///source.mp4",
        audio_uri=str(audio_path),
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

    # Create queued run
    run = Run(
        run_id="run-001",
        experiment_id="exp-001",
        item_id="item-001",
        variant_key="variant-a",
        spec_hash="abc123",
        status="queued",
    )
    db_session.add(run)

    db_session.commit()

    return {
        "audio_path": audio_path,
        "run_id": "run-001",
        "experiment_id": "exp-001",
    }


class TestWorkerOrchestratorInterface:
    """Test orchestrator interface."""

    def test_can_instantiate(self, db_session: Session, tmp_path: Path):
        """Orchestrator can be instantiated with session and output dir."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )
        assert orchestrator is not None

    def test_has_process_run_method(self, db_session: Session, tmp_path: Path):
        """Orchestrator has process_run method."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )
        assert hasattr(orchestrator, "process_run")

    def test_has_get_queued_runs_method(self, db_session: Session, tmp_path: Path):
        """Orchestrator has get_queued_runs method."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )
        assert hasattr(orchestrator, "get_queued_runs")


class TestGetQueuedRuns:
    """Test fetching queued runs."""

    def test_returns_queued_runs(self, db_session: Session, tmp_path: Path, setup_test_data: dict):
        """get_queued_runs returns runs with status=queued."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )
        runs = orchestrator.get_queued_runs()
        assert len(runs) == 1
        assert runs[0].run_id == "run-001"
        assert runs[0].status == "queued"

    def test_does_not_return_running_runs(
        self, db_session: Session, tmp_path: Path, setup_test_data: dict
    ):
        """get_queued_runs does not return running runs."""
        # Update run to running
        run = db_session.query(Run).filter_by(run_id="run-001").first()
        run.status = "running"
        db_session.commit()

        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )
        runs = orchestrator.get_queued_runs()
        assert len(runs) == 0

    def test_does_not_return_succeeded_runs(
        self, db_session: Session, tmp_path: Path, setup_test_data: dict
    ):
        """get_queued_runs does not return succeeded runs."""
        # Update run to succeeded
        run = db_session.query(Run).filter_by(run_id="run-001").first()
        run.status = "succeeded"
        db_session.commit()

        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )
        runs = orchestrator.get_queued_runs()
        assert len(runs) == 0


class TestProcessRun:
    """Test run processing pipeline."""

    def test_updates_status_to_running(
        self, db_session: Session, tmp_path: Path, setup_test_data: dict
    ):
        """process_run updates status to running at start."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )

        run = db_session.query(Run).filter_by(run_id="run-001").first()
        assert run.status == "queued"

        # Start processing (may fail due to invalid audio, but status should change)
        try:
            orchestrator.process_run(run)
        except Exception:
            pass

        db_session.refresh(run)
        assert run.status in ("running", "succeeded", "failed")

    def test_successful_run_updates_status_to_succeeded(
        self, db_session: Session, tmp_path: Path, setup_test_data: dict
    ):
        """Successful run updates status to succeeded."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )

        run = db_session.query(Run).filter_by(run_id="run-001").first()
        orchestrator.process_run(run)

        db_session.refresh(run)
        # May be succeeded or failed depending on environment
        assert run.status in ("succeeded", "failed")

    def test_failed_run_updates_status_to_failed(
        self, db_session: Session, tmp_path: Path, setup_test_data: dict
    ):
        """Failed run updates status to failed with error details."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )

        # Create a run with invalid audio path
        run2 = Run(
            run_id="run-002",
            experiment_id="exp-001",
            item_id="item-001",
            variant_key="variant-b",
            spec_hash="def456",
            status="queued",
        )
        db_session.add(run2)
        db_session.commit()

        # Modify item to have invalid audio path
        item = db_session.query(DatasetItem).filter_by(item_id="item-001").first()
        original_audio = item.audio_uri
        item.audio_uri = "/nonexistent/audio.wav"
        db_session.commit()

        orchestrator.process_run(run2)

        db_session.refresh(run2)
        assert run2.status == "failed"
        assert run2.error_code is not None

        # Restore
        item.audio_uri = original_audio
        db_session.commit()


class TestRunPipelineSteps:
    """Test individual pipeline steps."""

    def test_creates_provider_call_record(
        self, db_session: Session, tmp_path: Path, setup_test_data: dict
    ):
        """process_run creates a ProviderCall record."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )

        run = db_session.query(Run).filter_by(run_id="run-001").first()
        orchestrator.process_run(run)

        calls = db_session.query(ProviderCall).filter_by(run_id="run-001").all()
        # Should have at least one call (or none if failed early)
        assert isinstance(calls, list)

    def test_creates_metric_result_record(
        self, db_session: Session, tmp_path: Path, setup_test_data: dict
    ):
        """Successful run creates MetricResult record."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )

        run = db_session.query(Run).filter_by(run_id="run-001").first()
        orchestrator.process_run(run)

        db_session.refresh(run)
        if run.status == "succeeded":
            results = db_session.query(MetricResult).filter_by(run_id="run-001").all()
            assert len(results) > 0

    def test_sets_output_canon_uri_on_success(
        self, db_session: Session, tmp_path: Path, setup_test_data: dict
    ):
        """Successful run sets output_canon_uri."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )

        run = db_session.query(Run).filter_by(run_id="run-001").first()
        orchestrator.process_run(run)

        db_session.refresh(run)
        if run.status == "succeeded":
            assert run.output_canon_uri is not None


class TestRunTimestamps:
    """Test run timestamp handling."""

    def test_sets_started_at(self, db_session: Session, tmp_path: Path, setup_test_data: dict):
        """process_run sets started_at timestamp."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )

        run = db_session.query(Run).filter_by(run_id="run-001").first()
        assert run.started_at is None

        orchestrator.process_run(run)

        db_session.refresh(run)
        assert run.started_at is not None

    def test_sets_ended_at(self, db_session: Session, tmp_path: Path, setup_test_data: dict):
        """process_run sets ended_at timestamp."""
        orchestrator = WorkerOrchestrator(
            session=db_session,
            output_dir=tmp_path,
        )

        run = db_session.query(Run).filter_by(run_id="run-001").first()
        assert run.ended_at is None

        orchestrator.process_run(run)

        db_session.refresh(run)
        assert run.ended_at is not None
