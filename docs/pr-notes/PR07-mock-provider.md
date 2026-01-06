# PR07: Mock Provider Adapter

## Summary

Implements the mock provider adapter that returns cached or synthetically generated video for testing the pipeline without calling a real generation API.

## Files Changed

- `src/mirage/providers/__init__.py` - Package init
- `src/mirage/providers/base.py` - Abstract base class for providers
- `src/mirage/providers/mock.py` - Mock provider implementation
- `tests/test_providers.py` - 15 tests for provider behavior

## Implementation Details

### ProviderBase Interface

Abstract base class defining the provider contract:

```python
class ProviderBase(ABC):
    @abstractmethod
    def generate_variant(self, input: GenerationInput) -> RawArtifact:
        pass
```

Per ARCHITECTURE.md boundary C, providers must NOT:
- Write to database
- Compute metrics
- Shape UI output

### MockProvider Features

1. **Deterministic Job ID**: Computed from input parameters for idempotency
2. **Cached Video Support**: Uses pre-cached videos from `cache_dir` if available
3. **Synthetic Video Generation**: Falls back to generating minimal MP4-like files
4. **Zero Cost**: Returns `cost_usd=0.0` for mock provider

### Idempotency

The provider computes a deterministic job ID from:
- provider name
- model + version
- prompt template
- seed
- input audio SHA256
- ref image SHA256

Same inputs always produce the same job ID and output.

### Output Structure

```python
RawArtifact(
    raw_video_path="/output/dir/{job_id}.mp4",
    provider_job_id="{16-char-hex}",
    cost_usd=0.0,
    latency_ms={measured},
)
```

## Testing

```bash
pytest tests/test_providers.py -v
```

- 2 tests for ProviderBase interface
- 3 tests for MockProvider interface
- 5 tests for artifact creation
- 2 tests for idempotency
- 2 tests for video content
- 1 test for cached asset support

## Boundary Compliance

- `src/mirage/providers/` is boundary C (provider adapter)
- Narrow interface: `generate(input) -> raw_artifact`
- No DB writes, metric computation, or UI concerns

## Verification

```bash
ruff check .
ruff format --check .
pytest tests/ -v
```
