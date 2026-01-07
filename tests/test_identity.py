"""Tests for identity utilities.

Invariants from ARCHITECTURE.md:
1. spec_hash is deterministic and includes all input artifact hashes
2. run_id is deterministic given experiment/item/variant/spec_hash
3. provider_idempotency_key is deterministic given provider/spec_hash
4. Same inputs always produce same outputs (reproducibility)
5. Different inputs produce different outputs (collision resistance)
"""

from mirage.core.identity import (
    compute_provider_idempotency_key,
    compute_run_id,
    compute_spec_hash,
    seed_from_variant_key,
)


class TestSpecHash:
    """Tests for spec_hash computation."""

    def test_deterministic_same_inputs(self):
        """Same inputs should produce same spec_hash."""
        hash1 = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version="1.0",
            rendered_prompt="Generate talking head",
            params_json='{"temperature": 0.7}',
            seed=42,
            input_audio_sha256="abc123",
            ref_image_sha256="def456",
        )
        hash2 = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version="1.0",
            rendered_prompt="Generate talking head",
            params_json='{"temperature": 0.7}',
            seed=42,
            input_audio_sha256="abc123",
            ref_image_sha256="def456",
        )
        assert hash1 == hash2

    def test_different_seed_different_hash(self):
        """Different seed should produce different spec_hash."""
        hash1 = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version="1.0",
            rendered_prompt="Generate talking head",
            params_json='{"temperature": 0.7}',
            seed=42,
            input_audio_sha256="abc123",
            ref_image_sha256=None,
        )
        hash2 = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version="1.0",
            rendered_prompt="Generate talking head",
            params_json='{"temperature": 0.7}',
            seed=43,  # Different seed
            input_audio_sha256="abc123",
            ref_image_sha256=None,
        )
        assert hash1 != hash2

    def test_different_audio_hash_different_spec_hash(self):
        """Different input audio hash should produce different spec_hash."""
        hash1 = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version=None,
            rendered_prompt="Generate talking head",
            params_json="{}",
            seed=42,
            input_audio_sha256="audio_hash_1",
            ref_image_sha256=None,
        )
        hash2 = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version=None,
            rendered_prompt="Generate talking head",
            params_json="{}",
            seed=42,
            input_audio_sha256="audio_hash_2",  # Different audio
            ref_image_sha256=None,
        )
        assert hash1 != hash2

    def test_null_ref_image_handled(self):
        """Null ref_image_sha256 should be handled consistently."""
        hash1 = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version=None,
            rendered_prompt="test",
            params_json="{}",
            seed=1,
            input_audio_sha256="audio",
            ref_image_sha256=None,
        )
        hash2 = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version=None,
            rendered_prompt="test",
            params_json="{}",
            seed=1,
            input_audio_sha256="audio",
            ref_image_sha256=None,
        )
        assert hash1 == hash2

    def test_returns_hex_string(self):
        """spec_hash should return a hex string."""
        hash_val = compute_spec_hash(
            provider="mock",
            model="test",
            model_version=None,
            rendered_prompt="test",
            params_json="{}",
            seed=1,
            input_audio_sha256="audio",
            ref_image_sha256=None,
        )
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64  # SHA256 hex length
        assert all(c in "0123456789abcdef" for c in hash_val)


class TestRunId:
    """Tests for run_id computation."""

    def test_deterministic_same_inputs(self):
        """Same inputs should produce same run_id."""
        run_id1 = compute_run_id(
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123def456",
        )
        run_id2 = compute_run_id(
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123def456",
        )
        assert run_id1 == run_id2

    def test_different_experiment_different_run_id(self):
        """Different experiment should produce different run_id."""
        run_id1 = compute_run_id(
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
        )
        run_id2 = compute_run_id(
            experiment_id="exp-2",  # Different experiment
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
        )
        assert run_id1 != run_id2

    def test_different_variant_different_run_id(self):
        """Different variant should produce different run_id."""
        run_id1 = compute_run_id(
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
        )
        run_id2 = compute_run_id(
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=43",  # Different variant
            spec_hash="abc123",
        )
        assert run_id1 != run_id2

    def test_returns_hex_string(self):
        """run_id should return a hex string."""
        run_id = compute_run_id(
            experiment_id="exp-1",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash="abc123",
        )
        assert isinstance(run_id, str)
        assert len(run_id) == 64
        assert all(c in "0123456789abcdef" for c in run_id)


class TestProviderIdempotencyKey:
    """Tests for provider_idempotency_key computation."""

    def test_deterministic_same_inputs(self):
        """Same inputs should produce same key."""
        key1 = compute_provider_idempotency_key(
            provider="mock",
            spec_hash="abc123def456",
        )
        key2 = compute_provider_idempotency_key(
            provider="mock",
            spec_hash="abc123def456",
        )
        assert key1 == key2

    def test_different_provider_different_key(self):
        """Different provider should produce different key."""
        key1 = compute_provider_idempotency_key(
            provider="mock",
            spec_hash="abc123",
        )
        key2 = compute_provider_idempotency_key(
            provider="other",  # Different provider
            spec_hash="abc123",
        )
        assert key1 != key2

    def test_different_spec_hash_different_key(self):
        """Different spec_hash should produce different key."""
        key1 = compute_provider_idempotency_key(
            provider="mock",
            spec_hash="spec_hash_1",
        )
        key2 = compute_provider_idempotency_key(
            provider="mock",
            spec_hash="spec_hash_2",  # Different spec
        )
        assert key1 != key2

    def test_returns_hex_string(self):
        """Key should return a hex string."""
        key = compute_provider_idempotency_key(
            provider="mock",
            spec_hash="abc123",
        )
        assert isinstance(key, str)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestEndToEndIdentity:
    """Integration test for full identity chain."""

    def test_full_identity_chain(self):
        """Test complete identity chain is reproducible."""
        # Step 1: Compute spec_hash
        spec_hash = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version="1.0",
            rendered_prompt="Generate talking head",
            params_json='{"temperature": 0.7}',
            seed=42,
            input_audio_sha256="audio_abc123",
            ref_image_sha256="image_def456",
        )

        # Step 2: Compute run_id using spec_hash
        run_id = compute_run_id(
            experiment_id="exp-demo",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash=spec_hash,
        )

        # Step 3: Compute provider key using spec_hash
        provider_key = compute_provider_idempotency_key(
            provider="mock",
            spec_hash=spec_hash,
        )

        # Verify all are deterministic on second run
        spec_hash_2 = compute_spec_hash(
            provider="mock",
            model="test-model",
            model_version="1.0",
            rendered_prompt="Generate talking head",
            params_json='{"temperature": 0.7}',
            seed=42,
            input_audio_sha256="audio_abc123",
            ref_image_sha256="image_def456",
        )
        run_id_2 = compute_run_id(
            experiment_id="exp-demo",
            item_id="item-1",
            variant_key="seed=42",
            spec_hash=spec_hash_2,
        )
        provider_key_2 = compute_provider_idempotency_key(
            provider="mock",
            spec_hash=spec_hash_2,
        )

        assert spec_hash == spec_hash_2
        assert run_id == run_id_2
        assert provider_key == provider_key_2


class TestSeedFromVariantKey:
    """Tests for seed_from_variant_key extraction."""

    def test_extracts_seed_from_seed_format(self):
        """Should extract integer seed from 'seed=X' format."""
        assert seed_from_variant_key("seed=42") == 42
        assert seed_from_variant_key("seed=123") == 123
        assert seed_from_variant_key("seed=0") == 0
        assert seed_from_variant_key("seed=999999") == 999999

    def test_handles_negative_seed(self):
        """Should handle negative seed values."""
        assert seed_from_variant_key("seed=-1") == -1
        assert seed_from_variant_key("seed=-42") == -42

    def test_falls_back_to_hash_for_non_seed_format(self):
        """Should use SHA256 derivation for non-seed=X format."""
        # These should return consistent hash-derived values
        seed1 = seed_from_variant_key("custom_variant")
        seed2 = seed_from_variant_key("custom_variant")
        assert seed1 == seed2
        assert isinstance(seed1, int)

    def test_different_variants_different_derived_seeds(self):
        """Different variant keys should produce different derived seeds."""
        seed1 = seed_from_variant_key("variant_a")
        seed2 = seed_from_variant_key("variant_b")
        assert seed1 != seed2

    def test_invalid_seed_value_falls_back_to_hash(self):
        """Invalid seed value after 'seed=' should fall back to hash."""
        # 'seed=abc' can't be parsed as int, should use hash
        seed1 = seed_from_variant_key("seed=abc")
        seed2 = seed_from_variant_key("seed=abc")
        assert seed1 == seed2
        # Should be hash-derived, not 0 or error
        assert seed1 != 0
