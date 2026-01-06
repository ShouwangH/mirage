"""Audio RMS envelope extraction via ffmpeg.

Adapter for extracting audio envelope for lip-sync correlation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class AudioDecodeError(Exception):
    """Raised when audio decoding fails."""

    pass


def extract_rms_envelope(
    audio_path: Path,
    *,
    fps: float,
    num_frames: int,
    sample_rate: int = 16000,
    timeout_s: float = 30.0,
) -> list[float]:
    """Extract RMS envelope from audio file.

    Args:
        audio_path: Path to audio file.
        fps: Video frame rate (for frame-aligned windows).
        num_frames: Number of video frames to align with.
        sample_rate: Audio sample rate for extraction.
        timeout_s: Timeout for ffmpeg subprocess.

    Returns:
        List of RMS values per frame window.

    Raises:
        FileNotFoundError: If audio file doesn't exist.
        AudioDecodeError: If extraction fails.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if num_frames <= 0 or fps <= 0:
        return []

    try:
        import numpy as np
    except ImportError as e:
        raise AudioDecodeError("numpy required for envelope extraction") from e

    # Extract raw audio using ffmpeg
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(audio_path),
                "-f",
                "f32le",
                "-acodec",
                "pcm_f32le",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-",
            ],
            capture_output=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as e:
        raise AudioDecodeError(
            f"Audio extraction timed out after {timeout_s}s for {audio_path}"
        ) from e
    except FileNotFoundError as e:
        raise AudioDecodeError("ffmpeg not available") from e

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[:500]
        raise AudioDecodeError(f"ffmpeg failed: {stderr}")

    audio_data = np.frombuffer(result.stdout, dtype=np.float32)
    if len(audio_data) == 0:
        raise AudioDecodeError(f"No audio data extracted from {audio_path}")

    # Compute RMS per frame window
    samples_per_frame = int(sample_rate / fps)
    envelope = []

    for i in range(num_frames):
        start = i * samples_per_frame
        end = start + samples_per_frame

        if start >= len(audio_data):
            envelope.append(0.0)
        else:
            chunk = audio_data[start:end]
            rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) > 0 else 0.0
            envelope.append(rms)

    return envelope
