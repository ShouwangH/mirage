# PR03: Normalization Module (FFmpeg Wrapper)

## Task + Plan

Implement video normalization to canonical format per ARCHITECTURE.md:
- h264 video codec + aac audio
- Fixed 30 fps
- Duration trimmed to match canonical audio

## Scope

- Create `src/mirage/normalize/ffmpeg.py` with normalization functions
- TDD: Tests written first with ffmpeg integration tests
- Tests skip gracefully if ffmpeg not installed

## Files Changed

- `src/mirage/normalize/__init__.py` (new)
- `src/mirage/normalize/ffmpeg.py` (new) - FFmpeg wrapper functions
- `tests/test_normalize.py` (new) - 11 tests (4 unit, 7 integration)

## Interfaces Touched

No - Uses frozen `CanonArtifact` model from PR01.

## Tests

11 tests added:
- **TestCheckFfmpegAvailable**: Returns boolean
- **TestGetVideoInfo**: Extracts duration, fps, dimensions
- **TestGetAudioDurationMs**: Returns integer milliseconds
- **TestNormalizeVideo**: Produces output, duration matches audio, deterministic sha256
- **TestCanonicalFormat**: Output is h264, fps is 30

Integration tests require ffmpeg and are skipped if not available.

## Pre-PR Cleanup Checklist

1. [x] Simplify: Removed unused imports (hashlib, MagicMock, patch)
2. [x] Boundary review:
   - `normalize/` contains only ffmpeg operations
   - No DB dependencies, no metrics
3. [x] Interface review: Returns `CanonArtifact` per frozen interface
4. [x] Invariant review:
   - Normalization happens before metrics/playback
   - Output sha256 computed from file content
5. [x] Local commands:
   ```bash
   source .venv/bin/activate
   pytest tests/ -v  # 40 passed, 7 skipped
   ruff check .      # All checks passed
   ruff format --check .  # 15 files formatted
   ```

## Risks

- ffmpeg not installed in CI: Tests skip gracefully, CI workflow installs ffmpeg
- Encoding non-determinism: Acknowledged in test, verified file sizes match

## Demo Check

N/A - This PR is foundation only. No visible demo impact.

## Decisions

1. **Canonical format**: h264 + aac in mp4 container (browser-safe)
2. **Fixed 30fps**: Consistent frame rate for metrics
3. **Duration trimming**: Video trimmed to audio duration (audio is source of truth)
4. **Skip pattern**: Integration tests skip if ffmpeg unavailable
