"""FFmpeg-based video normalization.

Normalizes raw video to canonical format per ARCHITECTURE.md:
- mp4 container with h264 video + aac audio
- Fixed 30 fps
- Duration trimmed to match audio
"""

import hashlib
import json
import subprocess
from pathlib import Path

from mirage.models.types import CanonArtifact

# Canonical format settings
CANONICAL_FPS = 30
CANONICAL_VIDEO_CODEC = "libx264"
CANONICAL_AUDIO_CODEC = "aac"
CANONICAL_PIXEL_FORMAT = "yuv420p"


def check_ffmpeg_available() -> bool:
    """Check if ffmpeg and ffprobe are available.

    Returns:
        True if both ffmpeg and ffprobe are available.
    """
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_video_info(video_path: Path) -> dict:
    """Extract video information using ffprobe.

    Args:
        video_path: Path to video file.

    Returns:
        Dict with duration_ms, fps, width, height.

    Raises:
        FileNotFoundError: If video file doesn't exist.
        RuntimeError: If ffprobe fails.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,duration",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0]

    # Parse frame rate (fraction like "30/1")
    fps_str = stream.get("r_frame_rate", "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/")
        fps = int(num) / int(den)
    else:
        fps = float(fps_str)

    # Parse duration
    duration_str = stream.get("duration", "0")
    duration_ms = int(float(duration_str) * 1000)

    return {
        "duration_ms": duration_ms,
        "fps": fps,
        "width": stream.get("width", 0),
        "height": stream.get("height", 0),
    }


def get_audio_duration_ms(audio_path: Path) -> int:
    """Get audio duration in milliseconds.

    Args:
        audio_path: Path to audio file.

    Returns:
        Duration in milliseconds.

    Raises:
        FileNotFoundError: If audio file doesn't exist.
        RuntimeError: If ffprobe fails.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    duration_str = data.get("format", {}).get("duration", "0")
    return int(float(duration_str) * 1000)


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
        RuntimeError: If ffmpeg fails.
    """
    if not raw_video_path.exists():
        raise FileNotFoundError(f"Video file not found: {raw_video_path}")
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Get audio duration for trimming
    audio_duration_ms = get_audio_duration_ms(audio_path)
    audio_duration_sec = audio_duration_ms / 1000.0

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run ffmpeg normalization
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i",
            str(raw_video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",  # Video from first input
            "-map",
            "1:a:0",  # Audio from second input
            "-c:v",
            CANONICAL_VIDEO_CODEC,
            "-c:a",
            CANONICAL_AUDIO_CODEC,
            "-r",
            str(CANONICAL_FPS),
            "-pix_fmt",
            CANONICAL_PIXEL_FORMAT,
            "-t",
            str(audio_duration_sec),  # Trim to audio duration
            "-movflags",
            "+faststart",  # Browser-friendly
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=300,  # 5 minute timeout
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    # Compute sha256 of output
    sha256 = _compute_file_sha256(output_path)

    # Get actual output duration
    output_info = get_video_info(output_path)

    return CanonArtifact(
        canon_video_path=str(output_path),
        sha256=sha256,
        duration_ms=output_info["duration_ms"],
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
