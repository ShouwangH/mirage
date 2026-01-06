#!/usr/bin/env python3
"""Create demo assets for testing.

Creates minimal valid video and audio files for demo purposes.
"""

import subprocess
import sys
from pathlib import Path

DEMO_ASSETS_DIR = Path(__file__).parent.parent / "demo_assets"


def create_demo_video():
    """Create a minimal demo video using ffmpeg."""
    video_path = DEMO_ASSETS_DIR / "demo_source.mp4"

    if video_path.exists():
        print(f"Demo video already exists: {video_path}")
        return True

    try:
        # Create a 2-second test video with test pattern and sine wave audio
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=2:size=320x240:rate=30",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-shortest",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print(f"Created demo video: {video_path}")
            return True
        else:
            print(f"Failed to create demo video: {result.stderr}")
            return False

    except FileNotFoundError:
        print("ffmpeg not found. Please install ffmpeg to create demo assets.")
        return False
    except subprocess.TimeoutExpired:
        print("ffmpeg timed out")
        return False


def create_demo_audio():
    """Create a minimal demo audio file using ffmpeg."""
    audio_path = DEMO_ASSETS_DIR / "demo_audio.wav"

    if audio_path.exists():
        print(f"Demo audio already exists: {audio_path}")
        return True

    try:
        # Create a 2-second sine wave audio
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=2",
                "-c:a",
                "pcm_s16le",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print(f"Created demo audio: {audio_path}")
            return True
        else:
            print(f"Failed to create demo audio: {result.stderr}")
            return False

    except FileNotFoundError:
        print("ffmpeg not found. Please install ffmpeg to create demo assets.")
        return False
    except subprocess.TimeoutExpired:
        print("ffmpeg timed out")
        return False


def main():
    """Create all demo assets."""
    DEMO_ASSETS_DIR.mkdir(exist_ok=True)

    video_ok = create_demo_video()
    audio_ok = create_demo_audio()

    if video_ok and audio_ok:
        print("Demo assets created successfully!")
        return 0
    else:
        print("Some demo assets could not be created.")
        print("Please ensure ffmpeg is installed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
