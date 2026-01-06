# PR01: Project Scaffolding + Database Schema

## Task + Plan

Set up project foundation with:
1. Python package structure (src layout)
2. SQLite database schema with correctness invariants
3. Frozen pydantic models per IMPLEMENTATION_PLAN.md

## Scope

- Create `src/mirage/` package structure
- Implement database schema with unique constraints
- Implement frozen pydantic API models
- Set up pytest with TDD-first tests

## Files Changed

- `pyproject.toml` (new) - Package configuration
- `requirements.txt` (new) - Core dependencies
- `requirements-dev.txt` (new) - Dev dependencies
- `src/mirage/db/schema.py` (new) - SQLAlchemy models
- `src/mirage/models/types.py` (new) - Pydantic models
- `tests/conftest.py` (new) - Pytest fixtures
- `tests/test_db_schema.py` (new) - Schema invariant tests
- `tests/test_models.py` (new) - Model validation tests

## Interfaces Touched

Yes - This PR defines the frozen interfaces from IMPLEMENTATION_PLAN.md:
- `GenerationInput`, `RawArtifact`, `CanonArtifact`
- `MetricBundleV1`, `RunDetail`, `ExperimentOverview`
- `RatingSubmission`, `HumanSummary`

## Tests

22 tests added covering:
- Schema creation (8 tables)
- Run uniqueness constraint (experiment_id, item_id, variant_key)
- Provider call deduplication (provider, provider_idempotency_key)
- Metric result versioning (run_id, metric_name, metric_version)
- Pydantic model validation (literal types, optional fields)

## Pre-PR Cleanup Checklist

1. [x] Simplify: Removed unused imports (HumanTask, HumanRating in tests)
2. [x] Boundary review:
   - `db/` contains only schema definitions (no business logic)
   - `models/` contains only pydantic types (no DB dependencies)
3. [x] Interface review: Models match IMPLEMENTATION_PLAN.md exactly
4. [x] Invariant review:
   - UniqueConstraint on runs (experiment_id, item_id, variant_key)
   - UniqueConstraint on provider_calls (provider, provider_idempotency_key)
   - UniqueConstraint on metric_results (run_id, metric_name, metric_version)
5. [x] Local commands:
   ```bash
   source .venv/bin/activate
   pip install -e ".[dev]"
   pytest tests/ -v  # 22 passed
   ruff check .      # All checks passed
   ruff format --check .  # 10 files formatted
   ```

## Risks

- SQLite specific behavior for unique constraints (tested in memory)
- Python 3.10+ required for `X | None` syntax

## Demo Check

N/A - This PR is foundation only. No visible demo impact.

## Decisions

1. **src layout**: Using `src/mirage/` for cleaner imports and editable installs
2. **SQLAlchemy 2.0**: Using declarative mapped columns for type safety
3. **Pydantic v2**: Using modern pydantic with Literal types for validation
4. **Tests first**: All tests written before implementation (TDD)
