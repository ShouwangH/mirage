# PR02: Core Identity Utilities

## Task + Plan

Implement deterministic identity computation for:
- `spec_hash`: Hash of generation specification
- `run_id`: Hash of run identity
- `provider_idempotency_key`: Deduplication key for provider calls

## Scope

- Create `src/mirage/core/identity.py` with pure functions
- Follow ARCHITECTURE.md identity specifications
- TDD: Tests written first, then implementation

## Files Changed

- `src/mirage/core/identity.py` (new) - Identity computation functions
- `tests/test_identity.py` (new) - 14 tests for determinism and uniqueness

## Interfaces Touched

No - Uses frozen interfaces from PR01.

## Tests

14 tests added covering:
- **TestSpecHash**: Determinism, seed sensitivity, audio hash sensitivity, null handling
- **TestRunId**: Determinism, experiment/variant sensitivity
- **TestProviderIdempotencyKey**: Determinism, provider/spec_hash sensitivity
- **TestEndToEndIdentity**: Full identity chain reproducibility

## Pre-PR Cleanup Checklist

1. [x] Simplify: Removed unused pytest import
2. [x] Boundary review:
   - `core/identity.py` contains only pure hash functions
   - No DB dependencies, no side effects
3. [x] Interface review: No new models created
4. [x] Invariant review:
   - spec_hash includes all input artifact hashes
   - run_id includes spec_hash (meaning is stable)
   - provider_idempotency_key enables deduplication
5. [x] Local commands:
   ```bash
   source .venv/bin/activate
   pytest tests/ -v  # 36 passed
   ruff check .      # All checks passed
   ruff format --check .  # 12 files formatted
   ```

## Risks

None - Pure functions with no external dependencies.

## Demo Check

N/A - This PR is foundation only. No visible demo impact.

## Decisions

1. **Canonical JSON**: Using `json.dumps(sort_keys=True)` for deterministic serialization
2. **Delimiter**: Using `|` as delimiter in concatenations to prevent ambiguity
3. **SHA256**: Standard choice for content-addressable storage
