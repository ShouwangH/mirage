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
from pathlib import Path

from mirage.db import repo
from mirage.db.repo import DbSession
from mirage.models.domain import (
    MetricResultEntity,
    ProviderCallEntity,
    RunEntity,
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

    def __init__(self, session: DbSession, output_dir: Path):
        """Initialize orchestrator.

        Args:
            session: Database session for queries and updates.
            output_dir: Base directory for output artifacts.
        """
        self.session = session
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_queued_runs(self) -> list[RunEntity]:
        """Get all runs with status=queued.

        Returns:
            List of RunEntity objects ready for processing.
        """
        return repo.get_queued_runs(self.session)

    def process_run(self, run: RunEntity) -> None:
        """Process a single run through the pipeline.

        Pipeline steps:
        1. Update status to running
        2. Build GenerationInput from database
        3. Call provider to generate raw video
        4. Normalize video to canonical format
        5. Compute metrics
        6. Store results and update status

        Args:
            run: RunEntity object to process.
        """
        try:
            # Step 1: Update status to running
            repo.set_run_started(self.session, run.run_id)
            repo.commit(self.session)

            # Step 2: Build GenerationInput
            gen_input = self._build_generation_input(run)

            # Step 3: Call provider
            raw_artifact = self._call_provider(run, gen_input)

            # Step 4: Normalize video
            canon_artifact = self._normalize_video(run, raw_artifact, gen_input)

            # Step 5: Compute metrics
            self._compute_metrics(run, canon_artifact, gen_input)

            # Step 6: Update run with success
            repo.update_run_status(
                self.session,
                run.run_id,
                "succeeded",
                output_canon_uri=canon_artifact.canon_video_path,
                output_sha256=canon_artifact.sha256,
            )
            repo.set_run_ended(self.session, run.run_id)
            repo.commit(self.session)

        except Exception as e:
            # Handle failure
            repo.update_run_status(
                self.session,
                run.run_id,
                "failed",
                error_code=type(e).__name__,
                error_detail=str(e),
            )
            repo.set_run_ended(self.session, run.run_id)
            repo.commit(self.session)

    def _build_generation_input(self, run: RunEntity) -> GenerationInput:
        """Build GenerationInput from database records.

        Args:
            run: Run to build input for.

        Returns:
            GenerationInput with all required fields.

        Raises:
            ValueError: If required data is missing.
        """
        # Get dataset item via repository
        item = repo.get_dataset_item(self.session, run.item_id)
        if item is None:
            raise ValueError(f"DatasetItem not found: {run.item_id}")

        # Get experiment via repository
        experiment = repo.get_experiment(self.session, run.experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {run.experiment_id}")

        # Get generation spec via repository
        spec = repo.get_generation_spec(self.session, experiment.generation_spec_id)
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

        # Extract seed from variant_key using deterministic hash
        # (Python's built-in hash() is non-deterministic across processes)
        seed = int.from_bytes(
            hashlib.sha256(run.variant_key.encode("utf-8")).digest()[:4],
            byteorder="big",
        )

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

    def _call_provider(self, run: RunEntity, gen_input: GenerationInput):
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

        # Check for existing provider call via repository
        existing_call = repo.get_provider_call_by_idempotency_key(
            self.session, gen_input.provider, idempotency_key
        )

        if existing_call and existing_call.status == "completed":
            # Reuse existing result - return cached artifact
            from mirage.models.types import RawArtifact

            return RawArtifact(
                raw_video_path=str(
                    self.output_dir
                    / "runs"
                    / run.run_id
                    / "raw"
                    / f"{existing_call.provider_job_id}.mp4"
                ),
                provider_job_id=existing_call.provider_job_id,
                cost_usd=existing_call.cost_usd,
                latency_ms=existing_call.latency_ms,
            )

        # Create provider call record via repository
        provider_call_id = str(uuid.uuid4())
        provider_call = ProviderCallEntity(
            provider_call_id=provider_call_id,
            run_id=run.run_id,
            provider=gen_input.provider,
            provider_idempotency_key=idempotency_key,
            attempt=1,
            status="created",
        )
        repo.create_provider_call(self.session, provider_call)
        repo.commit(self.session)

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
            repo.update_provider_call(
                self.session,
                provider_call_id,
                status="completed",
                provider_job_id=raw_artifact.provider_job_id,
                cost_usd=raw_artifact.cost_usd,
                latency_ms=raw_artifact.latency_ms,
            )
            repo.commit(self.session)

            return raw_artifact

        except Exception:
            repo.update_provider_call(self.session, provider_call_id, status="failed")
            repo.commit(self.session)
            raise

    def _normalize_video(self, run: RunEntity, raw_artifact, gen_input: GenerationInput):
        """Normalize raw video to canonical format.

        Args:
            run: Current run.
            raw_artifact: Raw video from provider.
            gen_input: Generation input (for audio path).

        Returns:
            CanonArtifact with normalized video.
        """
        from mirage.normalize.video import normalize_video

        run_output_dir = self.output_dir / "runs" / run.run_id
        canon_path = run_output_dir / "output_canon.mp4"

        canon_artifact = normalize_video(
            raw_video_path=Path(raw_artifact.raw_video_path),
            audio_path=Path(gen_input.input_audio_path),
            output_path=canon_path,
        )

        return canon_artifact

    def _compute_metrics(self, run: RunEntity, canon_artifact, gen_input: GenerationInput):
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

        # Store metric result via repository
        metric_result = MetricResultEntity(
            metric_result_id=str(uuid.uuid4()),
            run_id=run.run_id,
            metric_name="MetricBundleV1",
            metric_version="1",
            value_json=metrics.model_dump_json(),
            status="computed",
        )
        repo.create_metric_result(self.session, metric_result)
        repo.commit(self.session)

        return metrics
