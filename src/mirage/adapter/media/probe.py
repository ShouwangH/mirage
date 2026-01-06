"""Media metadata probing via ffprobe.

Adapter for extracting video/audio metadata using ffprobe subprocess.
Handles timeouts, error handling, and output parsing.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoInfo:
    """Video stream information."""

    duration_ms: int
    fps: float
    frame_count: int
    width: int
    height: int


@dataclass
class AudioInfo:
    """Audio stream information."""

    duration_ms: int


def check_available() -> bool:
    """Check if media tools are available.

    Returns:
        True if ffmpeg and ffprobe are available.
    """
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def parse_fps(fps_str: str) -> float:
    """Parse fps from ffprobe format (e.g. '30/1' or '29.97').

    Args:
        fps_str: FPS string from ffprobe.

    Returns:
        FPS as float.
    """
    if "/" in fps_str:
        num, den = fps_str.split("/")
        return int(num) / int(den) if int(den) != 0 else 30.0
    return float(fps_str) if fps_str else 30.0


def probe_video(video_path: Path) -> VideoInfo:
    """Get video stream information.

    Args:
        video_path: Path to video file.

    Returns:
        VideoInfo with duration, fps, frame_count, dimensions.

    Raises:
        FileNotFoundError: If video file doesn't exist.
        RuntimeError: If probe fails or times out.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,duration,nb_frames",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as e:
        partial = e.stdout if e.stdout else "(no output)"
        raise RuntimeError(f"Video probe timed out for {video_path}: {partial}") from e

    if result.returncode != 0:
        raise RuntimeError(f"Video probe failed: {result.stderr}")

    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0]

    fps = parse_fps(stream.get("r_frame_rate", "30/1"))
    duration_ms = int(float(stream.get("duration", "0")) * 1000)

    # Frame count - use nb_frames if available, else estimate from duration
    nb_frames_str = stream.get("nb_frames", "")
    if nb_frames_str:
        frame_count = int(nb_frames_str)
    else:
        frame_count = int(duration_ms * fps / 1000) if duration_ms > 0 else 0

    return VideoInfo(
        duration_ms=duration_ms,
        fps=fps,
        frame_count=frame_count,
        width=int(stream.get("width", 0)),
        height=int(stream.get("height", 0)),
    )


def probe_audio(audio_path: Path) -> AudioInfo:
    """Get audio stream information.

    Args:
        audio_path: Path to audio file.

    Returns:
        AudioInfo with duration.

    Raises:
        FileNotFoundError: If audio file doesn't exist.
        RuntimeError: If probe fails or times out.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as e:
        partial = e.stdout if e.stdout else "(no output)"
        raise RuntimeError(f"Audio probe timed out for {audio_path}: {partial}") from e

    if result.returncode != 0:
        raise RuntimeError(f"Audio probe failed: {result.stderr}")

    data = json.loads(result.stdout)
    duration_str = data.get("format", {}).get("duration", "0")
    return AudioInfo(duration_ms=int(float(duration_str) * 1000))


def transcode_video(
    input_path: Path,
    audio_path: Path,
    output_path: Path,
    target_fps: float = 30.0,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
) -> None:
    """Transcode video to canonical format.

    Args:
        input_path: Source video file.
        audio_path: Audio file to mux.
        output_path: Output path for transcoded video.
        target_fps: Target frame rate.
        video_codec: Video codec to use.
        audio_codec: Audio codec to use.

    Raises:
        FileNotFoundError: If input files don't exist.
        RuntimeError: If transcode fails or times out.
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_path}")
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", str(input_path),
                "-i", str(audio_path),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", video_codec,
                "-c:a", audio_codec,
                "-r", str(target_fps),
                "-shortest",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"Transcode timed out for {input_path}") from e

    if result.returncode != 0:
        raise RuntimeError(f"Transcode failed: {result.stderr}")
