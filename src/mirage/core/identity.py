"""Identity utilities for deterministic IDs.

Implements identity computation from ARCHITECTURE.md:
- spec_hash: deterministic hash of generation spec
- run_id: deterministic hash of run identity
- provider_idempotency_key: deduplication key for provider calls
"""

import hashlib
import json


def compute_spec_hash(
    provider: str,
    model: str,
    model_version: str | None,
    rendered_prompt: str,
    params_json: str,
    seed: int,
    input_audio_sha256: str,
    ref_image_sha256: str | None,
) -> str:
    """Compute deterministic spec_hash.

    spec_hash = sha256(canonical_json({
        provider, model, model_version,
        rendered_prompt, params_json, seed,
        input_audio_sha256, ref_image_sha256
    }))

    Args:
        provider: Provider name (e.g., "mock")
        model: Model name
        model_version: Model version (nullable)
        rendered_prompt: Rendered prompt text
        params_json: JSON string of parameters
        seed: Random seed
        input_audio_sha256: SHA256 hash of input audio
        ref_image_sha256: SHA256 hash of reference image (nullable)

    Returns:
        64-character hex string (SHA256)
    """
    # Create canonical JSON object (sorted keys for determinism)
    spec_obj = {
        "provider": provider,
        "model": model,
        "model_version": model_version,
        "rendered_prompt": rendered_prompt,
        "params_json": params_json,
        "seed": seed,
        "input_audio_sha256": input_audio_sha256,
        "ref_image_sha256": ref_image_sha256,
    }

    # Canonical JSON: sorted keys, no whitespace
    canonical = json.dumps(spec_obj, sort_keys=True, separators=(",", ":"))

    # SHA256 hash
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_run_id(
    experiment_id: str,
    item_id: str,
    variant_key: str,
    spec_hash: str,
) -> str:
    """Compute deterministic run_id.

    run_id = sha256(experiment_id + item_id + variant_key + spec_hash)

    Args:
        experiment_id: Experiment identifier
        item_id: Dataset item identifier
        variant_key: Variant key (e.g., "seed=42")
        spec_hash: Pre-computed spec_hash

    Returns:
        64-character hex string (SHA256)
    """
    # Concatenate with delimiter to prevent ambiguity
    identity_str = f"{experiment_id}|{item_id}|{variant_key}|{spec_hash}"

    return hashlib.sha256(identity_str.encode("utf-8")).hexdigest()


def compute_provider_idempotency_key(
    provider: str,
    spec_hash: str,
) -> str:
    """Compute provider idempotency key.

    provider_idempotency_key = sha256(provider + spec_hash)

    Args:
        provider: Provider name
        spec_hash: Pre-computed spec_hash

    Returns:
        64-character hex string (SHA256)
    """
    # Concatenate with delimiter
    key_str = f"{provider}|{spec_hash}"

    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()
