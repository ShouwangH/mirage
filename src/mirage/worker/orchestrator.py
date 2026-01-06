"""Worker orchestrator for run processing.

Per ARCHITECTURE.md boundary B (worker/orchestrator):
- Performs expensive side effects: provider generation, normalization, metrics
- Owns retry/idempotency logic
- Forbidden: UI rendering concerns, no giant "manager" class

The orchestrator connects all pipeline components:
1. Provider (boundary C) - generates raw video
2. Normalizer - transcodes to canonical format
3. Metrics (boundary D) - computes MetricBundleV1
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from mirage.db.schema import (
    DatasetItem,
    GenerationSpec,
    MetricResult,
    ProviderCall,
    Run,
)
from mirage.models.types import GenerationInput
from mirage.providers.mock import MockProvider


class WorkerOrchestrator:
    """Orchestrates run processing through the pipeline.

    Responsibilities:
    - Fetch queued runs from database
    - Process each run through: provider -> normalize -> metrics
    - Update run status and store results
    - Handle errors and record failures
    """

    def __init__(self, session: Session, output_dir: Path):
        """Initialize orchestrator.

        Args:
            session: Database session for queries and updates.
            output_dir: Base directory for output artifacts.
        """
        self.session = session
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_queued_runs(self) -> list[Run]:
        """Get all runs with status=queued.

        Returns:
            List of Run objects ready for processing.
        """
        return self.session.query(Run).filter(Run.status == "queued").all()

    def process_run(self, run: Run) -> None:
        """Process a single run through the pipeline.

        Pipeline steps:
        1. Update status to running
        2. Build GenerationInput from database
        3. Call provider to generate raw video
        4. Normalize video to canonical format
        5. Compute metrics
        6. Store results and update status

        Args:
            run: Run object to process.
        """
        try:
            # Step 1: Update status to running
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            self.session.commit()

            # Step 2: Build GenerationInput
            gen_input = self._build_generation_input(run)

            # Step 3: Call provider
            raw_artifact = self._call_provider(run, gen_input)

            # Step 4: Normalize video
            canon_artifact = self._normalize_video(run, raw_artifact, gen_input)

            # Step 5: Compute metrics
            self._compute_metrics(run, canon_artifact, gen_input)

            # Step 6: Update run with success
            run.status = "succeeded"
            run.output_canon_uri = canon_artifact.canon_video_path
            run.output_sha256 = canon_artifact.sha256
            run.ended_at = datetime.now(timezone.utc)
            self.session.commit()

        except Exception as e:
            # Handle failure
            run.status = "failed"
            run.error_code = type(e).__name__
            run.error_detail = str(e)
            run.ended_at = datetime.now(timezone.utc)
            self.session.commit()

    def _build_generation_input(self, run: Run) -> GenerationInput:
        """Build GenerationInput from database records.

        Args:
            run: Run to build input for.

        Returns:
            GenerationInput with all required fields.

        Raises:
            ValueError: If required data is missing.
        """
        # Get dataset item
        item = self.session.query(DatasetItem).filter(DatasetItem.item_id == run.item_id).first()
        if item is None:
            raise ValueError(f"DatasetItem not found: {run.item_id}")

        # Get experiment and spec
        from mirage.db.schema import Experiment

        experiment = (
            self.session.query(Experiment)
            .filter(Experiment.experiment_id == run.experiment_id)
            .first()
        )
        if experiment is None:
            raise ValueError(f"Experiment not found: {run.experiment_id}")

        spec = (
            self.session.query(GenerationSpec)
            .filter(GenerationSpec.generation_spec_id == experiment.generation_spec_id)
            .first()
        )
        if spec is None:
            raise ValueError(f"GenerationSpec not found: {experiment.generation_spec_id}")

        # Compute audio SHA256
        audio_path = Path(item.audio_uri)
        if audio_path.exists():
            audio_sha256 = hashlib.sha256(audio_path.read_bytes()).hexdigest()
        else:
            raise FileNotFoundError(f"Audio file not found: {item.audio_uri}")

        # Compute ref image SHA256 if present
        ref_image_sha256 = None
        if item.ref_image_uri:
            ref_path = Path(item.ref_image_uri)
            if ref_path.exists():
                ref_image_sha256 = hashlib.sha256(ref_path.read_bytes()).hexdigest()

        # Parse params
        params = json.loads(spec.params_json) if spec.params_json else {}

        # Extract seed from variant_key or use default
        seed = hash(run.variant_key) % (2**32)

        return GenerationInput(
            provider=spec.provider,
            model=spec.model,
            model_version=spec.model_version,
            prompt_template=spec.prompt_template,
            params=params,
            seed=seed,
            input_audio_path=item.audio_uri,
            input_audio_sha256=audio_sha256,
            ref_image_path=item.ref_image_uri,
            ref_image_sha256=ref_image_sha256,
        )

    def _call_provider(self, run: Run, gen_input: GenerationInput):
        """Call provider to generate raw video.

        Args:
            run: Current run.
            gen_input: Generation input parameters.

        Returns:
            RawArtifact from provider.
        """
        from mirage.core.identity import compute_provider_idempotency_key

        # Compute idempotency key
        idempotency_key = compute_provider_idempotency_key(
            provider=gen_input.provider,
            spec_hash=run.spec_hash,
        )

        # Check for existing provider call
        existing_call = (
            self.session.query(ProviderCall)
            .filter(
                ProviderCall.provider == gen_input.provider,
                ProviderCall.provider_idempotency_key == idempotency_key,
            )
            .first()
        )

        if existing_call and existing_call.status == "completed":
            # Reuse existing result if available
            pass

        # Create provider call record
        provider_call = ProviderCall(
            provider_call_id=str(uuid.uuid4()),
            run_id=run.run_id,
            provider=gen_input.provider,
            provider_idempotency_key=idempotency_key,
            attempt=1,
            status="created",
        )
        self.session.add(provider_call)
        self.session.commit()

        # Create output directory for run
        run_output_dir = self.output_dir / "runs" / run.run_id
        run_output_dir.mkdir(parents=True, exist_ok=True)

        # Call provider (mock for now)
        provider = MockProvider(
            output_dir=run_output_dir / "raw",
        )

        try:
            raw_artifact = provider.generate_variant(gen_input)

            # Update provider call
            provider_call.status = "completed"
            provider_call.provider_job_id = raw_artifact.provider_job_id
            provider_call.cost_usd = raw_artifact.cost_usd
            provider_call.latency_ms = raw_artifact.latency_ms
            self.session.commit()

            return raw_artifact

        except Exception:
            provider_call.status = "failed"
            self.session.commit()
            raise

    def _normalize_video(self, run: Run, raw_artifact, gen_input: GenerationInput):
        """Normalize raw video to canonical format.

        Args:
            run: Current run.
            raw_artifact: Raw video from provider.
            gen_input: Generation input (for audio path).

        Returns:
            CanonArtifact with normalized video.
        """
        from mirage.normalize.ffmpeg import normalize_video

        run_output_dir = self.output_dir / "runs" / run.run_id
        canon_path = run_output_dir / "output_canon.mp4"

        canon_artifact = normalize_video(
            raw_video_path=Path(raw_artifact.raw_video_path),
            audio_path=Path(gen_input.input_audio_path),
            output_path=canon_path,
        )

        return canon_artifact

    def _compute_metrics(self, run: Run, canon_artifact, gen_input: GenerationInput):
        """Compute metrics for canonical video.

        Args:
            run: Current run.
            canon_artifact: Canonical video artifact.
            gen_input: Generation input (for audio path).

        Returns:
            MetricBundleV1 with all metrics.
        """
        from mirage.metrics.bundle import compute_metrics

        metrics = compute_metrics(
            video_path=Path(canon_artifact.canon_video_path),
            audio_path=Path(gen_input.input_audio_path),
        )

        # Store metric result
        metric_result = MetricResult(
            metric_result_id=str(uuid.uuid4()),
            run_id=run.run_id,
            metric_name="MetricBundleV1",
            metric_version="1",
            value_json=metrics.model_dump_json(),
            status="computed",
        )
        self.session.add(metric_result)
        self.session.commit()

        return metrics
