"""Base provider interface.

Per ARCHITECTURE.md boundary C:
- Provider adapter: narrow interface `generate(input) -> raw_artifact`
- Forbidden: DB writes, metric logic, UI shaping
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from mirage.models.types import GenerationInput, RawArtifact


class ProviderBase(ABC):
    """Abstract base class for generation providers.

    Providers implement a narrow interface: generate_variant(input) -> raw_artifact

    Per boundary rules, providers must NOT:
    - Write to database
    - Compute metrics
    - Shape UI output
    """

    @abstractmethod
    def generate_variant(self, input: GenerationInput) -> RawArtifact:
        """Generate a video variant from input.

        Args:
            input: Generation input with audio, prompt, and parameters.

        Returns:
            RawArtifact with path to generated video.
        """
        pass
