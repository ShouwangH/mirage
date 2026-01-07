"""Mock provider for demo/testing.

Returns cached or synthetically generated video for testing the pipeline
without calling a real generation API.

Per ARCHITECTURE.md boundary C:
- Provider adapter: narrow interface `generate(input) -> raw_artifact`
- Forbidden: DB writes, metric logic, UI shaping
"""

from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path

from mirage.models.types import GenerationInput, RawArtifact
from mirage.providers.base import ProviderBase


class MockProvider(ProviderBase):
    """Mock provider that returns cached or synthetic video.

    For demo purposes, this provider:
    1. Uses cached video if available in cache_dir
    2. Otherwise generates a minimal synthetic video

    Idempotency is guaranteed by using a deterministic job ID based on
    input parameters.
    """

    def __init__(self, output_dir: Path, cache_dir: Path | None = None):
        """Initialize mock provider.

        Args:
            output_dir: Directory to write output videos.
            cache_dir: Optional directory with pre-cached demo videos.
        """
        self.output_dir = Path(output_dir)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _compute_job_id(self, input: GenerationInput) -> str:
        """Compute deterministic job ID from input.

        This ensures idempotency - same input produces same job ID.
        """
        # Create hash from input parameters
        hash_input = (
            f"{input.provider}:{input.model}:{input.model_version}:"
            f"{input.prompt_template}:{input.seed}:{input.input_audio_sha256}:"
            f"{input.ref_image_sha256}"
        )
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _get_cached_video(self) -> Path | None:
        """Get a cached video from cache_dir if available."""
        if self.cache_dir is None or not self.cache_dir.exists():
            return None

        # Look for any mp4 file in cache
        for f in self.cache_dir.glob("*.mp4"):
            return f

        return None

    def _generate_synthetic_video(self, output_path: Path, seed: int) -> None:
        """Generate a synthetic test pattern video using ffmpeg.

        Creates a valid MP4 video with a test pattern that varies by seed.
        """
        import subprocess

        # Use seed to vary the test pattern color (hex format)
        # Convert seed to RGB hex color
        r = (seed * 37) % 256
        g = (seed * 59) % 256
        b = (seed * 97) % 256
        hex_color = f"0x{r:02x}{g:02x}{b:02x}"

        # Generate 3-second test pattern video with seed-based color
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={hex_color}:s=640x480:d=3",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:v",
                    "libx264",
                    "-t",
                    "3",
                    str(output_path),
                ],
                capture_output=True,
                check=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # Fallback: create minimal valid MP4 if ffmpeg unavailable
            raise RuntimeError(f"Failed to generate synthetic video: {e}") from e

    def generate_variant(self, input: GenerationInput) -> RawArtifact:
        """Generate a video variant.

        Args:
            input: Generation input parameters.

        Returns:
            RawArtifact with path to generated video.
        """
        start_time = time.time()

        # Compute deterministic job ID for idempotency
        job_id = self._compute_job_id(input)

        # Output path based on job ID
        output_path = self.output_dir / f"{job_id}.mp4"

        # Check if output already exists (idempotency)
        if not output_path.exists():
            # Try to use cached video first
            cached = self._get_cached_video()
            if cached:
                shutil.copy(cached, output_path)
            else:
                # Generate synthetic video
                self._generate_synthetic_video(output_path, input.seed)

        latency_ms = int((time.time() - start_time) * 1000)

        return RawArtifact(
            raw_video_path=str(output_path),
            provider_job_id=job_id,
            cost_usd=0.0,  # Mock provider is free
            latency_ms=latency_ms,
        )
