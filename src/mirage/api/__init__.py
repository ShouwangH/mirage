"""API module for Mirage.

Per ARCHITECTURE.md boundary A (api layer):
- Validates inputs, reads/writes DB
- Returns payloads for UI
- Forbidden: provider calls, ffmpeg work, metric computation
"""
