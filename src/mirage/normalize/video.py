"""Video normalization to canonical format.

Normalizes raw video to canonical format per ARCHITECTURE.md:
- mp4 container with h264 video + aac audio
- Fixed 30 fps
- Duration trimmed to match audio
"""

import hashlib
import subprocess
from pathlib import Path

from mirage.adapter.media import check_available, probe_audio, probe_video
from mirage.models.types import CanonArtifact

# Canonical format settings
CANONICAL_FPS = 30
CANONICAL_VIDEO_CODEC = "libx264"
CANONICAL_AUDIO_CODEC = "aac"
CANONICAL_PIXEL_FORMAT = "yuv420p"


def check_tools_available() -> bool:
    """Check if video processing tools are available.

    Returns:
        True if tools are available.
    """
    return check_available()


def normalize_video(
    raw_video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> CanonArtifact:
    """Normalize video to canonical format.

    Canonical format per ARCHITECTURE.md:
    - mp4 (h264 video + aac audio)
    - 30 fps
    - Duration trimmed to audio duration

    Args:
        raw_video_path: Path to raw video from provider.
        audio_path: Path to canonical audio (determines output duration).
        output_path: Path for normalized output.

    Returns:
        CanonArtifact with path, sha256, and duration_ms.

    Raises:
        FileNotFoundError: If input files don't exist.
        RuntimeError: If normalization fails.
    """
    if not raw_video_path.exists():
        raise FileNotFoundError(f"Video file not found: {raw_video_path}")
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Get audio duration for trimming
    audio_info = probe_audio(audio_path)
    audio_duration_sec = audio_info.duration_ms / 1000.0

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run normalization with specific settings for canonical format
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", str(raw_video_path),
                "-i", str(audio_path),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", CANONICAL_VIDEO_CODEC,
                "-c:a", CANONICAL_AUDIO_CODEC,
                "-r", str(CANONICAL_FPS),
                "-pix_fmt", CANONICAL_PIXEL_FORMAT,
                "-t", str(audio_duration_sec),
                "-movflags", "+faststart",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Normalization timed out for {raw_video_path}") from e

    if result.returncode != 0:
        raise RuntimeError(f"Normalization failed: {result.stderr}")

    # Compute sha256 of output
    sha256 = _compute_file_sha256(output_path)

    # Get actual output duration
    output_info = probe_video(output_path)

    return CanonArtifact(
        canon_video_path=str(output_path),
        sha256=sha256,
        duration_ms=output_info.duration_ms,
    )


def _compute_file_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file.

    Args:
        file_path: Path to file.

    Returns:
        64-character hex string.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
