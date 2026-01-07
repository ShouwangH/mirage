# PR15: Fix MockProvider Video Generation

## Summary
Fixed MockProvider to generate valid MP4 videos using ffmpeg instead of creating invalid binary files.

## Problem
MockProvider's `_generate_synthetic_video` was creating invalid MP4 files by manually writing fake binary headers with random content. This caused:
- "moov atom not found" errors during video normalization
- Demo pipeline failures when processing runs
- ffprobe validation failures

## Solution
Updated `_generate_synthetic_video` to use ffmpeg's lavfi (libavfilter virtual input) to generate real test pattern videos:

```python
def _generate_synthetic_video(self, output_path: Path, seed: int) -> None:
    # Convert seed to RGB hex color for visual distinction
    r = (seed * 37) % 256
    g = (seed * 59) % 256
    b = (seed * 97) % 256
    hex_color = f"0x{r:02x}{g:02x}{b:02x}"

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={hex_color}:s=640x480:d=3",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-t", "3",
        str(output_path),
    ], ...)
```

## Technical Details

### ffmpeg lavfi color source
- `color=c=0xRRGGBB` - Generates solid color frames
- `s=640x480` - Output resolution
- `d=3` - Duration in seconds
- `-pix_fmt yuv420p` - Pixel format for broad compatibility
- `-c:v libx264` - H.264 codec for valid MP4

### Seed-based color variation
Each seed produces a visually distinct color using prime multipliers:
- `r = (seed * 37) % 256`
- `g = (seed * 59) % 256`
- `b = (seed * 97) % 256`

## Files Changed
- `src/mirage/providers/mock.py` - Updated `_generate_synthetic_video`
- `demo_assets/demo_source.mp4` - Regenerated as real video
- `demo_assets/demo_audio.wav` - Regenerated as real audio

## Testing
- All 198 tests pass
- `python scripts/seed_demo.py` completes with all runs succeeded
- `python scripts/smoke_demo.py` passes all 5 checks

## Dependencies
- Requires ffmpeg installed on system
- Falls back to raising RuntimeError if ffmpeg unavailable
