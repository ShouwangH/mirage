#!/usr/bin/env python3
"""Smoke test for demo experiment.

PR13: Validates that the demo experiment was seeded correctly
and all metrics are computed properly.

Usage:
    python scripts/smoke_demo.py

Exit codes:
    0: All checks passed
    1: Some checks failed
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mirage.db.schema import Experiment, MetricResult, Run  # noqa: E402
from mirage.db.session import get_session  # noqa: E402
from mirage.models.types import MetricBundleV1  # noqa: E402

# Constants
DEMO_DB_PATH = PROJECT_ROOT / "demo.db"
DEMO_EXPERIMENT_ID = "demo"


def check_database_exists() -> bool:
    """Check that demo database exists."""
    if not DEMO_DB_PATH.exists():
        print(f"FAIL: Demo database not found: {DEMO_DB_PATH}")
        return False
    print(f"OK: Database exists: {DEMO_DB_PATH}")
    return True


def check_experiment_exists(session) -> bool:
    """Check that demo experiment exists."""
    experiment = (
        session.query(Experiment).filter(Experiment.experiment_id == DEMO_EXPERIMENT_ID).first()
    )

    if not experiment:
        print(f"FAIL: Experiment not found: {DEMO_EXPERIMENT_ID}")
        return False

    print(f"OK: Experiment exists: {DEMO_EXPERIMENT_ID}")
    print(f"    Status: {experiment.status}")
    return True


def check_runs_succeeded(session) -> bool:
    """Check that all runs succeeded."""
    runs = session.query(Run).filter(Run.experiment_id == DEMO_EXPERIMENT_ID).all()

    if not runs:
        print("FAIL: No runs found for experiment")
        return False

    print(f"OK: Found {len(runs)} runs")

    all_succeeded = True
    for run in runs:
        if run.status == "succeeded":
            print(f"    OK: {run.variant_key} - succeeded")
        else:
            print(f"    FAIL: {run.variant_key} - {run.status}")
            if run.error_detail:
                print(f"         Error: {run.error_detail}")
            all_succeeded = False

    return all_succeeded


def check_metrics_computed(session) -> bool:
    """Check that metrics were computed for all runs."""
    runs = (
        session.query(Run)
        .filter(
            Run.experiment_id == DEMO_EXPERIMENT_ID,
            Run.status == "succeeded",
        )
        .all()
    )

    if not runs:
        print("FAIL: No succeeded runs to check metrics")
        return False

    all_have_metrics = True
    for run in runs:
        metric_result = (
            session.query(MetricResult)
            .filter(
                MetricResult.run_id == run.run_id,
                MetricResult.metric_name == "MetricBundleV1",
            )
            .first()
        )

        if not metric_result:
            print(f"FAIL: No metrics for run {run.variant_key}")
            all_have_metrics = False
            continue

        print(f"OK: Metrics computed for {run.variant_key}")

    return all_have_metrics


def check_metric_bundle_keys(session) -> bool:
    """Check that MetricBundleV1 has all expected keys."""
    # Get expected fields from the model
    expected_fields = set(MetricBundleV1.model_fields.keys())

    # Required fields per METRICS.md
    required_fields = {
        # Video quality (Tier 0)
        "decode_ok",
        "video_duration_ms",
        "audio_duration_ms",
        "av_duration_delta_ms",
        "fps",
        "frame_count",
        "scene_cut_count",
        "freeze_frame_ratio",
        "flicker_score",
        "blur_score",
        "frame_diff_spike_count",
        # Face metrics (Tier 1)
        "face_present_ratio",
        "face_bbox_jitter",
        "landmark_jitter",
        "mouth_open_energy",
        "mouth_audio_corr",
        "blink_count",
        "blink_rate_hz",
        # SyncNet (Tier 2, optional)
        "lse_d",
        "lse_c",
        # Status
        "status_badge",
        "reasons",
    }

    # Validate model has expected fields
    if required_fields != expected_fields:
        missing = required_fields - expected_fields
        extra = expected_fields - required_fields
        print("FAIL: MetricBundleV1 field mismatch")
        if missing:
            print(f"    Missing: {missing}")
        if extra:
            print(f"    Extra: {extra}")
        return False

    print("OK: MetricBundleV1 has all required fields")

    # Validate a sample metric result from database
    runs = (
        session.query(Run)
        .filter(
            Run.experiment_id == DEMO_EXPERIMENT_ID,
            Run.status == "succeeded",
        )
        .first()
    )

    if runs:
        metric_result = (
            session.query(MetricResult)
            .filter(
                MetricResult.run_id == runs.run_id,
                MetricResult.metric_name == "MetricBundleV1",
            )
            .first()
        )

        if metric_result:
            try:
                value = json.loads(metric_result.value_json)
                stored_keys = set(value.keys())

                if stored_keys != required_fields:
                    missing = required_fields - stored_keys
                    extra = stored_keys - required_fields
                    print("FAIL: Stored metric keys mismatch")
                    if missing:
                        print(f"    Missing: {missing}")
                    if extra:
                        print(f"    Extra: {extra}")
                    return False

                print("OK: Stored metric has all required keys")

                # Validate status badge value
                status_badge = value.get("status_badge")
                if status_badge not in ("pass", "flagged", "reject"):
                    print(f"FAIL: Invalid status_badge: {status_badge}")
                    return False
                print(f"OK: status_badge = {status_badge}")

            except json.JSONDecodeError as e:
                print(f"FAIL: Could not parse metric JSON: {e}")
                return False

    return True


def check_demo_assets() -> bool:
    """Check that demo assets exist."""
    demo_assets_dir = PROJECT_ROOT / "demo_assets"
    video_path = demo_assets_dir / "demo_source.mp4"
    audio_path = demo_assets_dir / "demo_audio.wav"

    all_exist = True

    if video_path.exists():
        print(f"OK: Demo video exists: {video_path}")
    else:
        print(f"FAIL: Demo video not found: {video_path}")
        all_exist = False

    if audio_path.exists():
        print(f"OK: Demo audio exists: {audio_path}")
    else:
        print(f"FAIL: Demo audio not found: {audio_path}")
        all_exist = False

    return all_exist


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("Mirage Demo Smoke Test")
    print("=" * 60)

    checks_passed = 0
    checks_failed = 0

    # Check 1: Demo assets
    print("\n[1/5] Checking demo assets...")
    if check_demo_assets():
        checks_passed += 1
    else:
        checks_failed += 1

    # Check 2: Database exists
    print("\n[2/5] Checking database...")
    if not check_database_exists():
        checks_failed += 1
        print("\n" + "=" * 60)
        print(f"RESULT: {checks_passed} passed, {checks_failed} failed")
        print("Run 'python scripts/seed_demo.py' first!")
        print("=" * 60)
        return 1

    checks_passed += 1

    # Get database session
    session = get_session(DEMO_DB_PATH)

    try:
        # Check 3: Experiment exists
        print("\n[3/5] Checking experiment...")
        if check_experiment_exists(session):
            checks_passed += 1
        else:
            checks_failed += 1

        # Check 4: Runs succeeded
        print("\n[4/5] Checking runs...")
        if check_runs_succeeded(session):
            checks_passed += 1
        else:
            checks_failed += 1

        # Check 5: Metrics computed and valid
        print("\n[5/5] Checking metrics...")
        if check_metrics_computed(session) and check_metric_bundle_keys(session):
            checks_passed += 1
        else:
            checks_failed += 1

    finally:
        session.close()

    # Summary
    print("\n" + "=" * 60)
    if checks_failed == 0:
        print(f"RESULT: ALL PASSED ({checks_passed} checks)")
        print("=" * 60)
        return 0
    else:
        print(f"RESULT: {checks_passed} passed, {checks_failed} failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
