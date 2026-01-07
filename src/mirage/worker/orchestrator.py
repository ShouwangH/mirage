"""Worker orchestrator for run processing.

Per ARCHITECTURE.md boundary B (worker/orchestrator):
- Performs expensive side effects: provider generation, normalization, metrics
- Owns retry/idempotency logic
- Forbidden: UI rendering concerns, no giant "manager" class

Architecture:
- WorkerOrchestrator: thin layer that claims runs and delegates to RunProcessor
- RunProcessor: pure orchestration for a single run
- RunContext: pre-built context with all data needed for processing
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from mirage.core.identity import (
    compute_provider_idempotency_key,
    seed_from_variant_key,
    sha256_file,
)
from mirage.db import repo
from mirage.db.repo import DbSession
from mirage.models.domain import (
    MetricResultEntity,
    ProviderCallEntity,
    RunEntity,
)
from mirage.models.types import GenerationInput, RawArtifact
from mirage.providers.mock import MockProvider


@dataclass
class RunContext:
    """Pre-built context for processing a single run.

    Contains all paths, IDs, and inputs needed for processing,
    avoiding repeated database lookups during processing.
    """

    run_id: str
    experiment_id: str
    item_id: str
    variant_key: str
    spec_hash: str
    gen_input: GenerationInput
    run_output_dir: Path


class RunProcessor:
    """Processes a single run through the pipeline.

    Pure orchestration: provider -> normalize -> metrics.
    Does not handle status updates or error wrapping - that's the orchestrator's job.
    """

    def __init__(self, session: DbSession, context: RunContext):
        """Initialize processor.

        Args:
            session: Database session for provider call records.
            context: Pre-built run context.
        """
        self.session = session
        self.ctx = context
        self.ctx.run_output_dir.mkdir(parents=True, exist_ok=True)

    def execute(self) -> tuple[str, str]:
        """Execute the full processing pipeline.

        Returns:
            Tuple of (canon_video_path, canon_sha256).
        """
        raw_artifact = self._call_provider()
        canon_artifact = self._normalize_video(raw_artifact)
        self._compute_metrics(canon_artifact)
        return canon_artifact.canon_video_path, canon_artifact.sha256

    def _call_provider(self) -> RawArtifact:
        """Call provider to generate raw video.

        Returns:
            RawArtifact from provider (either cached or freshly generated).
        """
        # Compute idempotency key
        idempotency_key = compute_provider_idempotency_key(
            provider=self.ctx.gen_input.provider,
            spec_hash=self.ctx.spec_hash,
        )

        # Check for existing provider call
        existing_call = repo.get_provider_call_by_idempotency_key(
            self.session, self.ctx.gen_input.provider, idempotency_key
        )

        if existing_call and existing_call.status == "completed":
            # Reuse existing result - use DB-stored artifact path
            if existing_call.raw_artifact_uri is None:
                raise ValueError(
                    f"Completed provider call {existing_call.provider_call_id} "
                    "missing raw_artifact_uri"
                )
            return RawArtifact(
                raw_video_path=existing_call.raw_artifact_uri,
                provider_job_id=existing_call.provider_job_id,
                cost_usd=existing_call.cost_usd,
                latency_ms=existing_call.latency_ms,
            )

        # Create provider call record
        provider_call_id = str(uuid.uuid4())
        provider_call = ProviderCallEntity(
            provider_call_id=provider_call_id,
            run_id=self.ctx.run_id,
            provider=self.ctx.gen_input.provider,
            provider_idempotency_key=idempotency_key,
            attempt=1,
            status="created",
        )
        repo.create_provider_call(self.session, provider_call)
        repo.commit(self.session)

        # Output path: artifacts/runs/{run_id}/raw/raw.mp4 (stable, not job_id based)
        raw_output_dir = self.ctx.run_output_dir / "raw"
        raw_output_dir.mkdir(parents=True, exist_ok=True)

        # Call provider (mock for now)
        provider = MockProvider(output_dir=raw_output_dir)

        try:
            raw_artifact = provider.generate_variant(self.ctx.gen_input)

            # Compute raw artifact SHA256
            raw_sha256 = sha256_file(Path(raw_artifact.raw_video_path))

            # Update provider call with artifact info
            repo.update_provider_call(
                self.session,
                provider_call_id,
                status="completed",
                provider_job_id=raw_artifact.provider_job_id,
                cost_usd=raw_artifact.cost_usd,
                latency_ms=raw_artifact.latency_ms,
                raw_artifact_uri=raw_artifact.raw_video_path,
                raw_artifact_sha256=raw_sha256,
            )
            repo.commit(self.session)

            return raw_artifact

        except Exception:
            repo.update_provider_call(self.session, provider_call_id, status="failed")
            repo.commit(self.session)
            raise

    def _normalize_video(self, raw_artifact: RawArtifact):
        """Normalize raw video to canonical format.

        Args:
            raw_artifact: Raw video from provider.

        Returns:
            CanonArtifact with normalized video.
        """
        from mirage.normalize.video import normalize_video

        canon_path = self.ctx.run_output_dir / "output_canon.mp4"

        canon_artifact = normalize_video(
            raw_video_path=Path(raw_artifact.raw_video_path),
            audio_path=Path(self.ctx.gen_input.input_audio_path),
            output_path=canon_path,
        )

        return canon_artifact

    def _compute_metrics(self, canon_artifact) -> None:
        """Compute metrics for canonical video.

        Args:
            canon_artifact: Canonical video artifact.
        """
        from mirage.metrics.bundle import compute_metrics

        metrics = compute_metrics(
            video_path=Path(canon_artifact.canon_video_path),
            audio_path=Path(self.ctx.gen_input.input_audio_path),
        )

        # Store metric result
        metric_result = MetricResultEntity(
            metric_result_id=str(uuid.uuid4()),
            run_id=self.ctx.run_id,
            metric_name="MetricBundleV1",
            metric_version="1",
            value_json=metrics.model_dump_json(),
            status="computed",
        )
        repo.create_metric_result(self.session, metric_result)
        repo.commit(self.session)


class WorkerOrchestrator:
    """Orchestrates run processing through the pipeline.

    Thin layer that:
    - Claims queued runs atomically
    - Builds RunContext from database
    - Delegates to RunProcessor
    - Handles status updates and error recording
    """

    def __init__(self, session: DbSession, output_dir: Path, worker_id: str = "default"):
        """Initialize orchestrator.

        Args:
            session: Database session for queries and updates.
            output_dir: Base directory for output artifacts.
            worker_id: Identifier for this worker (for atomic claiming).
        """
        self.session = session
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.worker_id = worker_id

    def get_queued_runs(self) -> list[RunEntity]:
        """Get all runs with status=queued.

        Returns:
            List of RunEntity objects ready for processing.
        """
        return repo.get_queued_runs(self.session)

    def claim_runs(self, limit: int = 1) -> list[RunEntity]:
        """Atomically claim queued runs for processing.

        Args:
            limit: Maximum number of runs to claim.

        Returns:
            List of claimed RunEntity objects (now with status='running').
        """
        return repo.claim_queued_runs(self.session, limit, self.worker_id)

    def process_run(self, run: RunEntity) -> None:
        """Process a single run through the pipeline.

        Wraps RunProcessor with status updates and error handling.

        Args:
            run: RunEntity object to process.
        """
        try:
            # Build context (may fail if data is missing)
            context = self._build_context(run)

            # If run wasn't already claimed (e.g., called directly), mark as running
            if run.status == "queued":
                repo.set_run_started(self.session, run.run_id)
                repo.commit(self.session)

            # Process with RunProcessor
            processor = RunProcessor(self.session, context)
            canon_uri, canon_sha256 = processor.execute()

            # Update run with success
            repo.update_run_status(
                self.session,
                run.run_id,
                "succeeded",
                output_canon_uri=canon_uri,
                output_sha256=canon_sha256,
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

    def _build_context(self, run: RunEntity) -> RunContext:
        """Build RunContext from database records.

        Args:
            run: Run to build context for.

        Returns:
            RunContext with all required fields.

        Raises:
            ValueError: If required data is missing.
            FileNotFoundError: If input files don't exist.
        """
        # Get dataset item
        item = repo.get_dataset_item(self.session, run.item_id)
        if item is None:
            raise ValueError(f"DatasetItem not found: {run.item_id}")

        # Get experiment
        experiment = repo.get_experiment(self.session, run.experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment not found: {run.experiment_id}")

        # Get generation spec
        spec = repo.get_generation_spec(self.session, experiment.generation_spec_id)
        if spec is None:
            raise ValueError(f"GenerationSpec not found: {experiment.generation_spec_id}")

        # Compute audio SHA256 (streaming)
        audio_path = Path(item.audio_uri)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {item.audio_uri}")
        audio_sha256 = sha256_file(audio_path)

        # Compute ref image SHA256 if present (streaming)
        ref_image_sha256 = None
        if item.ref_image_uri:
            ref_path = Path(item.ref_image_uri)
            if ref_path.exists():
                ref_image_sha256 = sha256_file(ref_path)

        # Parse params
        params = json.loads(spec.params_json) if spec.params_json else {}

        # Extract seed from variant_key using centralized function
        seed = seed_from_variant_key(run.variant_key)

        gen_input = GenerationInput(
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

        run_output_dir = self.output_dir / "runs" / run.run_id

        return RunContext(
            run_id=run.run_id,
            experiment_id=run.experiment_id,
            item_id=run.item_id,
            variant_key=run.variant_key,
            spec_hash=run.spec_hash,
            gen_input=gen_input,
            run_output_dir=run_output_dir,
        )
