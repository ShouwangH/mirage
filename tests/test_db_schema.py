"""Tests for database schema invariants.

Invariants from DATA_MODEL.md:
1. Runs unique per (experiment_id, item_id, variant_key)
2. Provider spend deduped by (provider, provider_idempotency_key)
3. Metric results unique per (run_id, metric_name, metric_version)
4. State transitions are monotonic (succeeded/failed are terminal)
"""

import pytest
from sqlalchemy.exc import IntegrityError

from mirage.db.schema import (
    Base,
    DatasetItem,
    Experiment,
    GenerationSpec,
    MetricResult,
    ProviderCall,
    Run,
)


class TestSchemaCreation:
    """Test that schema can be created without errors."""

    def test_all_tables_created(self, engine):
        """All required tables should exist after creation."""
        table_names = Base.metadata.tables.keys()
        expected_tables = {
            "dataset_items",
            "generation_specs",
            "experiments",
            "runs",
            "provider_calls",
            "metric_results",
            "human_tasks",
            "human_ratings",
        }
        assert expected_tables.issubset(table_names)


class TestRunUniqueness:
    """Invariant: runs unique per (experiment_id, item_id, variant_key)."""

    def test_can_create_run(self, session):
        """Basic run creation should work."""
        item = DatasetItem(
            item_id="item-1",
            subject_id="subject-1",
            source_video_uri="video.mp4",
            audio_uri="audio.wav",
        )
        spec = GenerationSpec(
            generation_spec_id="spec-1",
            provider="mock",
            model="test-model",
            prompt_template="test prompt",
        )
        experiment = Experiment(
            experiment_id="exp-1",
            generation_spec_id="spec-1",
            status="draft",
        )
        run = Run(
            run_id="run-1",
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
            status="queued",
        )
        session.add_all([item, spec, experiment, run])
        session.commit()

        assert session.query(Run).count() == 1

    def test_duplicate_run_rejected(self, session):
        """Duplicate (experiment, item, variant) should be rejected."""
        item = DatasetItem(
            item_id="item-1",
            subject_id="subject-1",
            source_video_uri="video.mp4",
            audio_uri="audio.wav",
        )
        spec = GenerationSpec(
            generation_spec_id="spec-1",
            provider="mock",
            model="test-model",
            prompt_template="test prompt",
        )
        experiment = Experiment(
            experiment_id="exp-1",
            generation_spec_id="spec-1",
            status="draft",
        )
        run1 = Run(
            run_id="run-1",
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
            status="queued",
        )
        session.add_all([item, spec, experiment, run1])
        session.commit()

        # Try to create duplicate
        run2 = Run(
            run_id="run-2",  # Different run_id
            experiment_id="exp-1",  # Same experiment
            item_id="item-1",  # Same item
            variant_key="seed=42",  # Same variant - should fail
            spec_hash="def456",
            status="queued",
        )
        session.add(run2)
        with pytest.raises(IntegrityError):
            session.commit()


class TestProviderCallDeduplication:
    """Invariant: provider calls deduped by (provider, provider_idempotency_key)."""

    def test_can_create_provider_call(self, session):
        """Basic provider call creation should work."""
        # Setup required entities
        item = DatasetItem(
            item_id="item-1",
            subject_id="subject-1",
            source_video_uri="video.mp4",
            audio_uri="audio.wav",
        )
        spec = GenerationSpec(
            generation_spec_id="spec-1",
            provider="mock",
            model="test-model",
            prompt_template="test prompt",
        )
        experiment = Experiment(
            experiment_id="exp-1",
            generation_spec_id="spec-1",
            status="draft",
        )
        run = Run(
            run_id="run-1",
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
            status="queued",
        )
        session.add_all([item, spec, experiment, run])
        session.commit()

        call = ProviderCall(
            provider_call_id="call-1",
            run_id="run-1",
            provider="mock",
            provider_idempotency_key="key-123",
            attempt=1,
            status="in_flight",
        )
        session.add(call)
        session.commit()

        assert session.query(ProviderCall).count() == 1

    def test_duplicate_provider_call_rejected(self, session):
        """Duplicate (provider, idempotency_key) should be rejected."""
        # Setup
        item = DatasetItem(
            item_id="item-1",
            subject_id="subject-1",
            source_video_uri="video.mp4",
            audio_uri="audio.wav",
        )
        spec = GenerationSpec(
            generation_spec_id="spec-1",
            provider="mock",
            model="test-model",
            prompt_template="test prompt",
        )
        experiment = Experiment(
            experiment_id="exp-1",
            generation_spec_id="spec-1",
            status="draft",
        )
        run = Run(
            run_id="run-1",
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
            status="queued",
        )
        session.add_all([item, spec, experiment, run])
        session.commit()

        call1 = ProviderCall(
            provider_call_id="call-1",
            run_id="run-1",
            provider="mock",
            provider_idempotency_key="key-123",
            attempt=1,
            status="in_flight",
        )
        session.add(call1)
        session.commit()

        # Try duplicate
        call2 = ProviderCall(
            provider_call_id="call-2",  # Different ID
            run_id="run-1",
            provider="mock",  # Same provider
            provider_idempotency_key="key-123",  # Same key - should fail
            attempt=2,
            status="in_flight",
        )
        session.add(call2)
        with pytest.raises(IntegrityError):
            session.commit()


class TestMetricResultUniqueness:
    """Invariant: metric results unique per (run_id, metric_name, metric_version)."""

    def test_can_create_metric_result(self, session):
        """Basic metric result creation should work."""
        # Setup
        item = DatasetItem(
            item_id="item-1",
            subject_id="subject-1",
            source_video_uri="video.mp4",
            audio_uri="audio.wav",
        )
        spec = GenerationSpec(
            generation_spec_id="spec-1",
            provider="mock",
            model="test-model",
            prompt_template="test prompt",
        )
        experiment = Experiment(
            experiment_id="exp-1",
            generation_spec_id="spec-1",
            status="draft",
        )
        run = Run(
            run_id="run-1",
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
            status="succeeded",
        )
        session.add_all([item, spec, experiment, run])
        session.commit()

        metric = MetricResult(
            metric_result_id="metric-1",
            run_id="run-1",
            metric_name="decode_ok",
            metric_version="v1",
            value_json='{"value": true}',
            status="succeeded",
        )
        session.add(metric)
        session.commit()

        assert session.query(MetricResult).count() == 1

    def test_duplicate_metric_rejected(self, session):
        """Duplicate (run_id, metric_name, metric_version) should be rejected."""
        # Setup
        item = DatasetItem(
            item_id="item-1",
            subject_id="subject-1",
            source_video_uri="video.mp4",
            audio_uri="audio.wav",
        )
        spec = GenerationSpec(
            generation_spec_id="spec-1",
            provider="mock",
            model="test-model",
            prompt_template="test prompt",
        )
        experiment = Experiment(
            experiment_id="exp-1",
            generation_spec_id="spec-1",
            status="draft",
        )
        run = Run(
            run_id="run-1",
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
            status="succeeded",
        )
        session.add_all([item, spec, experiment, run])
        session.commit()

        metric1 = MetricResult(
            metric_result_id="metric-1",
            run_id="run-1",
            metric_name="decode_ok",
            metric_version="v1",
            value_json='{"value": true}',
            status="succeeded",
        )
        session.add(metric1)
        session.commit()

        # Try duplicate
        metric2 = MetricResult(
            metric_result_id="metric-2",  # Different ID
            run_id="run-1",  # Same run
            metric_name="decode_ok",  # Same name
            metric_version="v1",  # Same version - should fail
            value_json='{"value": false}',
            status="succeeded",
        )
        session.add(metric2)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_different_versions_allowed(self, session):
        """Different versions of same metric should be allowed."""
        # Setup
        item = DatasetItem(
            item_id="item-1",
            subject_id="subject-1",
            source_video_uri="video.mp4",
            audio_uri="audio.wav",
        )
        spec = GenerationSpec(
            generation_spec_id="spec-1",
            provider="mock",
            model="test-model",
            prompt_template="test prompt",
        )
        experiment = Experiment(
            experiment_id="exp-1",
            generation_spec_id="spec-1",
            status="draft",
        )
        run = Run(
            run_id="run-1",
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
            status="succeeded",
        )
        session.add_all([item, spec, experiment, run])
        session.commit()

        metric_v1 = MetricResult(
            metric_result_id="metric-1",
            run_id="run-1",
            metric_name="decode_ok",
            metric_version="v1",
            value_json='{"value": true}',
            status="succeeded",
        )
        metric_v2 = MetricResult(
            metric_result_id="metric-2",
            run_id="run-1",
            metric_name="decode_ok",
            metric_version="v2",  # Different version - should work
            value_json='{"value": true}',
            status="succeeded",
        )
        session.add_all([metric_v1, metric_v2])
        session.commit()

        assert session.query(MetricResult).count() == 2
