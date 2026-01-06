#!/usr/bin/env python3
"""Seed demo experiment with cached artifacts.

PR13: Creates a complete demo experiment that can be used to validate
the full pipeline: generation -> normalization -> metrics -> status.

Usage:
    python scripts/seed_demo.py

This script:
1. Creates demo video/audio assets if missing
2. Initializes the demo database
3. Seeds dataset item, generation spec, and experiment
4. Creates runs for multiple seed variants
5. Processes runs through the worker pipeline
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mirage.core.identity import compute_run_id, compute_spec_hash  # noqa: E402
from mirage.db.schema import DatasetItem, Experiment, GenerationSpec, Run  # noqa: E402
from mirage.db.session import get_session  # noqa: E402

# Constants
DEMO_DB_PATH = PROJECT_ROOT / "demo.db"
DEMO_ASSETS_DIR = PROJECT_ROOT / "demo_assets"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

# Demo identifiers
DEMO_EXPERIMENT_ID = "demo"
DEMO_ITEM_ID = "demo_item"
DEMO_SPEC_ID = "demo_spec"

# Variant seeds for demo
DEMO_SEEDS = [42, 123, 456]


def create_demo_assets() -> tuple[Path, Path]:
    """Create demo video and audio files using ffmpeg.

    Returns:
        Tuple of (video_path, audio_path)
    """
    DEMO_ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    video_path = DEMO_ASSETS_DIR / "demo_source.mp4"
    audio_path = DEMO_ASSETS_DIR / "demo_audio.wav"

    # Create video if missing
    if not video_path.exists():
        print("Creating demo video...")
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=2:size=320x240:rate=30",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=2",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-pix_fmt",
                    "yuv420p",
                    "-shortest",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print(f"Warning: Could not create demo video: {result.stderr}")
                # Create minimal placeholder for testing without ffmpeg
                video_path.write_bytes(b"minimal video placeholder")
            else:
                print(f"Created: {video_path}")
        except FileNotFoundError:
            print("Warning: ffmpeg not found, creating placeholder video")
            video_path.write_bytes(b"minimal video placeholder")
        except subprocess.TimeoutExpired:
            print("Warning: ffmpeg timed out, creating placeholder video")
            video_path.write_bytes(b"minimal video placeholder")

    # Create audio if missing
    if not audio_path.exists():
        print("Creating demo audio...")
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=2",
                    "-c:a",
                    "pcm_s16le",
                    str(audio_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                print(f"Warning: Could not create demo audio: {result.stderr}")
                # Create minimal placeholder for testing without ffmpeg
                audio_path.write_bytes(b"minimal audio placeholder")
            else:
                print(f"Created: {audio_path}")
        except FileNotFoundError:
            print("Warning: ffmpeg not found, creating placeholder audio")
            audio_path.write_bytes(b"minimal audio placeholder")
        except subprocess.TimeoutExpired:
            print("Warning: ffmpeg timed out, creating placeholder audio")
            audio_path.write_bytes(b"minimal audio placeholder")

    return video_path, audio_path


def compute_file_sha256(path: Path) -> str:
    """Compute SHA256 hash of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seed_database(video_path: Path, audio_path: Path) -> None:
    """Seed the demo database with experiment data.

    Args:
        video_path: Path to demo video file.
        audio_path: Path to demo audio file.
    """
    # Get session for demo database
    session = get_session(DEMO_DB_PATH)

    try:
        # Check if already seeded
        existing = (
            session.query(Experiment).filter(Experiment.experiment_id == DEMO_EXPERIMENT_ID).first()
        )

        if existing:
            print(f"Demo experiment already exists: {DEMO_EXPERIMENT_ID}")
            return

        # 1. Create DatasetItem
        print("Creating dataset item...")
        dataset_item = DatasetItem(
            item_id=DEMO_ITEM_ID,
            subject_id="demo_subject",
            source_video_uri=str(video_path.absolute()),
            audio_uri=str(audio_path.absolute()),
            ref_image_uri=None,
            metadata_json=json.dumps({"type": "demo", "duration_s": 2.0}),
        )
        session.add(dataset_item)

        # 2. Create GenerationSpec
        print("Creating generation spec...")
        generation_spec = GenerationSpec(
            generation_spec_id=DEMO_SPEC_ID,
            provider="mock",
            model="mock-v1",
            model_version="1.0",
            prompt_template="Generate a talking head video.",
            params_json=json.dumps({"quality": "demo"}),
            seed_policy_json=json.dumps({"seeds": DEMO_SEEDS}),
        )
        session.add(generation_spec)

        # 3. Create Experiment
        print("Creating experiment...")
        experiment = Experiment(
            experiment_id=DEMO_EXPERIMENT_ID,
            generation_spec_id=DEMO_SPEC_ID,
            status="running",
        )
        session.add(experiment)

        # 4. Create Runs for each seed
        print("Creating runs...")
        audio_sha256 = compute_file_sha256(audio_path)

        for seed in DEMO_SEEDS:
            variant_key = f"seed={seed}"

            # Compute spec_hash per ARCHITECTURE.md
            spec_hash = compute_spec_hash(
                provider="mock",
                model="mock-v1",
                model_version="1.0",
                rendered_prompt="Generate a talking head video.",
                params_json=json.dumps({"quality": "demo"}),
                seed=seed,
                input_audio_sha256=audio_sha256,
                ref_image_sha256=None,
            )

            # Compute run_id per ARCHITECTURE.md
            run_id = compute_run_id(
                experiment_id=DEMO_EXPERIMENT_ID,
                item_id=DEMO_ITEM_ID,
                variant_key=variant_key,
                spec_hash=spec_hash,
            )

            run = Run(
                run_id=run_id,
                experiment_id=DEMO_EXPERIMENT_ID,
                item_id=DEMO_ITEM_ID,
                variant_key=variant_key,
                spec_hash=spec_hash,
                status="queued",
            )
            session.add(run)
            print(f"  Created run: {variant_key} ({run_id[:8]}...)")

        session.commit()
        print("Database seeded successfully!")

    finally:
        session.close()


def process_runs() -> None:
    """Process queued runs through the worker pipeline."""
    from mirage.worker.orchestrator import WorkerOrchestrator

    session = get_session(DEMO_DB_PATH)

    try:
        orchestrator = WorkerOrchestrator(
            session=session,
            output_dir=ARTIFACTS_DIR,
        )

        queued_runs = orchestrator.get_queued_runs()
        print(f"Processing {len(queued_runs)} queued runs...")

        for run in queued_runs:
            print(f"  Processing: {run.variant_key}...")
            orchestrator.process_run(run)

            if run.status == "succeeded":
                print("    Status: succeeded")
            else:
                print(f"    Status: {run.status} - {run.error_detail}")

        # Update experiment status
        experiment = (
            session.query(Experiment).filter(Experiment.experiment_id == DEMO_EXPERIMENT_ID).first()
        )

        if experiment:
            # Check if all runs completed
            all_runs = session.query(Run).filter(Run.experiment_id == DEMO_EXPERIMENT_ID).all()

            if all(r.status in ("succeeded", "failed") for r in all_runs):
                experiment.status = "complete"
                session.commit()
                print("Experiment marked complete!")

    finally:
        session.close()


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("Mirage Demo Seeding Script")
    print("=" * 60)

    # Step 1: Create demo assets
    print("\n[1/3] Creating demo assets...")
    video_path, audio_path = create_demo_assets()

    # Step 2: Seed database
    print("\n[2/3] Seeding database...")
    seed_database(video_path, audio_path)

    # Step 3: Process runs
    print("\n[3/3] Processing runs...")
    process_runs()

    print("\n" + "=" * 60)
    print("Demo seeding complete!")
    print(f"Database: {DEMO_DB_PATH}")
    print(f"Artifacts: {ARTIFACTS_DIR}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
