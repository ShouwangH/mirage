"""Tests for provider adapters.

TDD: Tests written first per IMPLEMENTATION_PLAN.md.
"""

from pathlib import Path

import pytest

from mirage.models.types import GenerationInput, RawArtifact
from mirage.providers.base import ProviderBase
from mirage.providers.mock import MockProvider


@pytest.fixture
def sample_input(tmp_path: Path) -> GenerationInput:
    """Create a sample GenerationInput for testing."""
    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"fake audio content")

    ref_image_path = tmp_path / "ref.png"
    ref_image_path.write_bytes(b"fake image content")

    return GenerationInput(
        provider="mock",
        model="test-model",
        model_version="1.0",
        prompt_template="Generate a talking head video",
        params={"quality": "high"},
        seed=42,
        input_audio_path=str(audio_path),
        input_audio_sha256="abc123",
        ref_image_path=str(ref_image_path),
        ref_image_sha256="def456",
    )


class TestProviderBase:
    """Test base provider interface."""

    def test_is_abstract(self):
        """ProviderBase cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ProviderBase()

    def test_defines_generate_variant_method(self):
        """ProviderBase defines generate_variant signature."""
        assert hasattr(ProviderBase, "generate_variant")


class TestMockProviderInterface:
    """Test MockProvider implements correct interface."""

    def test_inherits_from_base(self):
        """MockProvider inherits from ProviderBase."""
        assert issubclass(MockProvider, ProviderBase)

    def test_can_instantiate(self, tmp_path: Path):
        """MockProvider can be instantiated with output directory."""
        provider = MockProvider(output_dir=tmp_path)
        assert provider is not None

    def test_generate_variant_returns_raw_artifact(
        self, tmp_path: Path, sample_input: GenerationInput
    ):
        """generate_variant returns RawArtifact."""
        provider = MockProvider(output_dir=tmp_path)
        result = provider.generate_variant(sample_input)
        assert isinstance(result, RawArtifact)


class TestMockProviderArtifactCreation:
    """Test MockProvider creates valid artifacts."""

    def test_creates_video_file(self, tmp_path: Path, sample_input: GenerationInput):
        """generate_variant creates a video file."""
        provider = MockProvider(output_dir=tmp_path)
        result = provider.generate_variant(sample_input)

        video_path = Path(result.raw_video_path)
        assert video_path.exists()
        assert video_path.stat().st_size > 0

    def test_video_path_under_output_dir(self, tmp_path: Path, sample_input: GenerationInput):
        """Generated video is placed under output_dir."""
        provider = MockProvider(output_dir=tmp_path)
        result = provider.generate_variant(sample_input)

        video_path = Path(result.raw_video_path)
        assert str(video_path).startswith(str(tmp_path))

    def test_returns_provider_job_id(self, tmp_path: Path, sample_input: GenerationInput):
        """generate_variant returns a provider job ID."""
        provider = MockProvider(output_dir=tmp_path)
        result = provider.generate_variant(sample_input)
        assert result.provider_job_id is not None
        assert len(result.provider_job_id) > 0

    def test_returns_latency_ms(self, tmp_path: Path, sample_input: GenerationInput):
        """generate_variant returns latency in ms."""
        provider = MockProvider(output_dir=tmp_path)
        result = provider.generate_variant(sample_input)
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    def test_returns_zero_cost_for_mock(self, tmp_path: Path, sample_input: GenerationInput):
        """Mock provider returns zero cost."""
        provider = MockProvider(output_dir=tmp_path)
        result = provider.generate_variant(sample_input)
        assert result.cost_usd == 0.0


class TestMockProviderIdempotency:
    """Test MockProvider idempotency behavior."""

    def test_same_input_same_seed_produces_same_output(
        self, tmp_path: Path, sample_input: GenerationInput
    ):
        """Same input with same seed produces identical output."""
        provider = MockProvider(output_dir=tmp_path)

        result1 = provider.generate_variant(sample_input)
        result2 = provider.generate_variant(sample_input)

        # Same job ID for idempotency
        assert result1.provider_job_id == result2.provider_job_id

        # Same video content
        video1 = Path(result1.raw_video_path).read_bytes()
        video2 = Path(result2.raw_video_path).read_bytes()
        assert video1 == video2

    def test_different_seed_produces_different_job_id(self, tmp_path: Path):
        """Different seed produces different job ID."""
        audio_path = tmp_path / "audio.wav"
        audio_path.write_bytes(b"audio")

        input1 = GenerationInput(
            provider="mock",
            model="test",
            model_version=None,
            prompt_template="test",
            params={},
            seed=42,
            input_audio_path=str(audio_path),
            input_audio_sha256="abc",
            ref_image_path=None,
            ref_image_sha256=None,
        )

        input2 = GenerationInput(
            provider="mock",
            model="test",
            model_version=None,
            prompt_template="test",
            params={},
            seed=43,  # Different seed
            input_audio_path=str(audio_path),
            input_audio_sha256="abc",
            ref_image_path=None,
            ref_image_sha256=None,
        )

        provider = MockProvider(output_dir=tmp_path)
        result1 = provider.generate_variant(input1)
        result2 = provider.generate_variant(input2)

        assert result1.provider_job_id != result2.provider_job_id


class TestMockProviderVideoContent:
    """Test MockProvider generates valid video content."""

    def test_generates_mp4_file(self, tmp_path: Path, sample_input: GenerationInput):
        """Generated file has .mp4 extension."""
        provider = MockProvider(output_dir=tmp_path)
        result = provider.generate_variant(sample_input)

        video_path = Path(result.raw_video_path)
        assert video_path.suffix == ".mp4"

    def test_video_has_minimum_size(self, tmp_path: Path, sample_input: GenerationInput):
        """Generated video has reasonable minimum size."""
        provider = MockProvider(output_dir=tmp_path)
        result = provider.generate_variant(sample_input)

        video_path = Path(result.raw_video_path)
        # Synthetic video should be at least a few KB
        assert video_path.stat().st_size >= 100


class TestMockProviderWithCachedAssets:
    """Test MockProvider with pre-cached demo assets."""

    def test_uses_cached_asset_if_available(self, tmp_path: Path):
        """Provider uses cached asset when available."""
        # Create a cache directory with a pre-made video
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        cached_video = cache_dir / "demo_video.mp4"
        cached_video.write_bytes(b"cached video content for demo")

        audio_path = tmp_path / "audio.wav"
        audio_path.write_bytes(b"audio")

        input_data = GenerationInput(
            provider="mock",
            model="test",
            model_version=None,
            prompt_template="test",
            params={},
            seed=42,
            input_audio_path=str(audio_path),
            input_audio_sha256="abc",
            ref_image_path=None,
            ref_image_sha256=None,
        )

        provider = MockProvider(output_dir=tmp_path, cache_dir=cache_dir)
        result = provider.generate_variant(input_data)

        # Should return a valid artifact
        assert isinstance(result, RawArtifact)
        assert Path(result.raw_video_path).exists()
