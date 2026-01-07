# ADR-0002: Repository Pattern for Database Access

## status
accepted

## context
SQLAlchemy imports and ORM entities were leaking throughout the codebase:
- `from sqlalchemy.orm import Session` in api/, eval/, aggregation/, worker/
- `from mirage.db.schema import Run, HumanTask, ...` in business logic
- Domain logic coupled to ORM implementation details

This caused:
1. Difficulty testing without real database
2. Schema changes rippling through entire codebase
3. Unclear boundaries between persistence and domain logic

## decision
Implement repository pattern with complete SQLAlchemy encapsulation:

**Domain models** (`models/domain.py`):
- Pure Python dataclasses (no ORM dependencies)
- RunEntity, TaskEntity, RatingEntity, ProviderCallEntity, etc.
- Used throughout the application

**Repository layer** (`db/repo.py`):
- All SQLAlchemy queries encapsulated here
- Converts SQLAlchemy models to domain entities
- Exports `DbSession` type alias for external use
- External code never imports from `db/schema.py`

**Type alias**:
```python
if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DbSession
else:
    DbSession = Session
```
Allows type hints without runtime SQLAlchemy import in dependent modules.

## consequences

**enables:**
- Business logic uses pure Python dataclasses
- Schema changes isolated to db/ directory
- Easier to mock for testing
- Clear dependency direction: domain → repo → schema

**makes harder:**
- Extra conversion step (ORM → domain) adds some overhead
- Must keep domain models in sync with schema
- Repository functions can become numerous

## alternatives considered

**use SQLAlchemy models directly:**
- Rejected: couples entire codebase to ORM

**use SQLModel (pydantic + sqlalchemy):**
- Rejected: adds dependency; dataclasses sufficient for MVP

**abstract repository interface:**
- Rejected: overkill; single implementation sufficient for MVP
