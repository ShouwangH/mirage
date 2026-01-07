# ADR-0001: Orchestrator/Processor Separation

## status
accepted

## context
The original WorkerOrchestrator class was doing too much:
- Claiming runs from the queue
- Building generation inputs from database lookups
- Calling providers
- Normalizing video
- Computing metrics
- Updating run status
- Handling errors

This made it difficult to:
1. Test processing logic in isolation
2. Reason about what happens during a single run vs orchestration
3. Reuse the processing logic in different contexts (e.g., CLI vs worker)

Additionally:
- SHA256 computation was reading entire files into memory
- Cache hits were reconstructing artifact paths instead of reading from DB
- Run claiming wasn't atomic (race conditions possible with multiple workers)

## decision
Split into three components:

**RunContext** (dataclass):
- Immutable container with all data needed to process a run
- Contains: run_id, experiment_id, item_id, variant_key, spec_hash, gen_input, run_output_dir
- Built once from database, then passed to processor

**RunProcessor** (pure processing):
- Takes a RunContext and DbSession
- Executes: provider → normalize → metrics
- Returns (canon_uri, canon_sha256) or raises
- No status management; caller handles that

**WorkerOrchestrator** (thin coordination):
- Claims runs atomically via `SELECT ... FOR UPDATE SKIP LOCKED`
- Builds RunContext from database
- Wraps RunProcessor with try/except for status updates
- Handles error recording

Supporting changes:
- `sha256_file()` in identity.py streams in 64KB chunks
- `seed_from_variant_key()` centralized in identity.py
- `raw_artifact_uri` stored in provider_calls for cache reuse
- Raw artifacts named `{run_id}/raw/raw.mp4` (stable, not job_id based)

## consequences

**enables:**
- RunProcessor can be unit tested with mock context
- Processing logic is reusable outside worker context
- Atomic claiming prevents double-processing
- Memory-efficient hashing for large video files
- Cache hits use DB-stored paths (no guessing)

**makes harder:**
- Slightly more indirection when tracing run processing
- Must remember to build RunContext before processing

## alternatives considered

**keep monolithic orchestrator:**
- Rejected: testing and maintenance burden too high

**use celery/dramatiq for claiming:**
- Rejected: overkill for local MVP; adds external dependency

**store artifacts by content hash (CAS):**
- Rejected: run_id-based paths are simpler and sufficient for MVP
- Could revisit if we need deduplication across experiments
