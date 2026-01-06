# SETUP.md — dependencies + environment

## system dependencies (required)
### ffmpeg
you must have both `ffmpeg` and `ffprobe` on PATH.

verify:
- `ffmpeg -version`
- `ffprobe -version`

mac:
- `brew install ffmpeg`

ubuntu:
- `sudo apt-get update && sudo apt-get install -y ffmpeg`

## python environment (recommended)
- python 3.10+
- create venv:
  - `python -m venv .venv`
  - `source .venv/bin/activate`
- install:
  - `pip install -r requirements.txt`

### optional: syncnet
syncnet requires torch and an evaluator repo/weights.
install only if you have time:
- `pip install -r requirements-syncnet.txt`

## node environment (if UI uses next.js)
- node 18+
- `npm install`
- `npm run dev`

## env vars
copy:
- `cp .env.example .env`

expected vars (example):
- PROVIDER_NAME=...
- PROVIDER_API_KEY=...
- DEMO_EXPERIMENT_ID=demo

## demo assets
place in:
- `demo_assets/source.mp4`
- `demo_assets/ref.png` (optional)
- `demo_assets/audio.wav` (optional; if missing we extract from source)

## canonical transcode rules
all generated outputs are normalized to browser-safe mp4:
- h264 video + aac audio
- fixed fps target (30)
- duration trimming policy: trim video to audio duration
