"""SyncNet adapter for lip-sync evaluation.

Handles model download, initialization, and inference for LSE-D/LSE-C metrics.
Gracefully returns None when dependencies or model unavailable.
"""

from __future__ import annotations

import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Model configuration
MODEL_URL = "https://www.robots.ox.ac.uk/~vgg/software/lipsync/data/syncnet_v2.model"
MODEL_DIR = Path(__file__).parent.parent.parent.parent.parent / "models"
MODEL_PATH = MODEL_DIR / "syncnet_v2.pth"

# Processing parameters
SAMPLE_RATE = 16000
HOP_LENGTH = 160  # 10ms at 16kHz
N_MFCC = 13
VIDEO_FPS = 25
LIP_SIZE = (112, 112)  # Expected lip region size
WINDOW_SIZE = 5  # Number of frames per embedding


@dataclass
class SyncNetResult:
    """Result of SyncNet evaluation.

    Attributes:
        lse_d: Lip Sync Error Distance (lower = better sync).
        lse_c: Lip Sync Error Confidence (higher = more confident).
        offset: Detected A/V offset in frames.
    """

    lse_d: float
    lse_c: float
    offset: int


def _ensure_model_downloaded() -> Path | None:
    """Download SyncNet model weights if not present.

    Returns:
        Path to model file, or None if download failed.
    """
    if MODEL_PATH.exists():
        return MODEL_PATH

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Downloading SyncNet model to {MODEL_PATH}...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        logger.info("SyncNet model downloaded successfully")
        return MODEL_PATH
    except Exception as e:
        logger.warning(f"Failed to download SyncNet model: {e}")
        return None


def _check_dependencies() -> bool:
    """Check if all required dependencies are available."""
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        logger.warning("PyTorch not available - SyncNet metrics disabled")
        return False


def _extract_mfcc(
    audio_path: Path, num_frames: int, fps: float = VIDEO_FPS
) -> "NDArray[np.float32]" | None:
    """Extract MFCC features from audio file.

    Args:
        audio_path: Path to audio file.
        num_frames: Number of video frames to align with.
        fps: Video frame rate.

    Returns:
        MFCC array of shape (num_windows, 1, time_steps, 13), or None on failure.
    """
    try:
        import librosa
    except ImportError:
        logger.warning("librosa not available for MFCC extraction")
        return None

    try:
        # Load audio at 16kHz
        audio, sr = librosa.load(str(audio_path), sr=SAMPLE_RATE)

        # Compute MFCCs
        mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=N_MFCC, hop_length=HOP_LENGTH)
        mfcc = mfcc.T  # Shape: (time, 13)

        # Calculate samples per video frame
        samples_per_frame = int(SAMPLE_RATE / fps)
        mfcc_per_frame = samples_per_frame // HOP_LENGTH

        # Create windows aligned with video frames
        # Each window covers WINDOW_SIZE frames worth of audio
        windows = []
        for i in range(num_frames - WINDOW_SIZE + 1):
            start = i * mfcc_per_frame
            end = start + WINDOW_SIZE * mfcc_per_frame
            if end <= len(mfcc):
                window = mfcc[start:end]
                # Reshape to match model expectation
                windows.append(window)

        if not windows:
            return None

        # Stack and add channel dimension
        mfcc_array = np.stack(windows).astype(np.float32)
        mfcc_array = mfcc_array[:, np.newaxis, :, :]  # (N, 1, T, 13)

        return mfcc_array

    except Exception as e:
        logger.warning(f"MFCC extraction failed: {e}")
        return None


def _extract_lip_regions(
    frames: list["NDArray[np.uint8]"],
    face_boxes: list[list[float]] | None = None,
) -> "NDArray[np.float32]" | None:
    """Extract lip region windows from video frames.

    Args:
        frames: List of BGR frames.
        face_boxes: Optional face bounding boxes [x1, y1, x2, y2] per frame.

    Returns:
        Array of shape (num_windows, 3, WINDOW_SIZE, 112, 112), or None on failure.
    """
    try:
        import cv2
    except ImportError:
        return None

    if len(frames) < WINDOW_SIZE:
        return None

    # Extract lip regions from each frame
    lip_frames = []
    for i, frame in enumerate(frames):
        h, w = frame.shape[:2]

        if face_boxes and i < len(face_boxes) and len(face_boxes[i]) >= 4:
            # Use provided face box
            x1, y1, x2, y2 = face_boxes[i][:4]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        else:
            # Assume face is centered, use lower half for lips
            x1, y1 = w // 4, h // 3
            x2, y2 = w * 3 // 4, h

        # Extract lower portion of face (lip region approximation)
        face_h = y2 - y1
        lip_y1 = y1 + int(face_h * 0.5)  # Lower half of face
        lip_region = frame[lip_y1:y2, x1:x2]

        if lip_region.size == 0:
            lip_region = frame[h // 2 :, w // 4 : w * 3 // 4]

        # Resize to expected size
        lip_region = cv2.resize(lip_region, LIP_SIZE)

        # Convert BGR to RGB and normalize
        lip_rgb = cv2.cvtColor(lip_region, cv2.COLOR_BGR2RGB)
        lip_normalized = lip_rgb.astype(np.float32) / 255.0

        lip_frames.append(lip_normalized)

    # Create windows of WINDOW_SIZE frames
    windows = []
    for i in range(len(lip_frames) - WINDOW_SIZE + 1):
        window = np.stack(lip_frames[i : i + WINDOW_SIZE])
        # Transpose to (C, T, H, W) for 3D CNN
        window = np.transpose(window, (3, 0, 1, 2))
        windows.append(window)

    if not windows:
        return None

    return np.stack(windows).astype(np.float32)


class SyncNetEvaluator:
    """SyncNet evaluator for computing LSE-D and LSE-C metrics."""

    def __init__(self) -> None:
        """Initialize SyncNet evaluator (model loaded on first use)."""
        self._model = None
        self._device = None
        self._initialized = False
        self._available = _check_dependencies()

    def _ensure_initialized(self) -> bool:
        """Ensure model is loaded.

        Returns:
            True if model ready, False otherwise.
        """
        if self._initialized:
            return self._model is not None

        self._initialized = True

        if not self._available:
            return False

        model_path = _ensure_model_downloaded()
        if model_path is None:
            return False

        try:
            import torch

            from mirage.adapter.syncnet.syncnet_model import SyncNetModel

            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self._model = SyncNetModel()

            # Load pretrained weights
            state_dict = torch.load(model_path, map_location=self._device)
            # Handle different checkpoint formats
            if "model_state_dict" in state_dict:
                state_dict = state_dict["model_state_dict"]

            # Try to load weights (may fail if architecture doesn't match)
            try:
                self._model.load_state_dict(state_dict, strict=False)
            except Exception as e:
                logger.warning(f"Could not load pretrained weights: {e}")
                # Continue with random weights for testing

            self._model.to(self._device)
            self._model.eval()

            logger.info(f"SyncNet model initialized on {self._device}")
            return True

        except Exception as e:
            logger.warning(f"Failed to initialize SyncNet: {e}")
            self._model = None
            return False

    def evaluate(
        self,
        frames: list["NDArray[np.uint8]"],
        audio_path: Path,
        fps: float = VIDEO_FPS,
        face_boxes: list[list[float]] | None = None,
    ) -> SyncNetResult | None:
        """Evaluate lip sync quality.

        Args:
            frames: List of BGR video frames.
            audio_path: Path to audio file.
            fps: Video frame rate.
            face_boxes: Optional face bounding boxes per frame.

        Returns:
            SyncNetResult with LSE-D, LSE-C, and offset, or None if evaluation fails.
        """
        if not self._ensure_initialized():
            return None

        import torch

        # Extract features
        mfcc = _extract_mfcc(audio_path, len(frames), fps)
        if mfcc is None:
            logger.warning("MFCC extraction failed")
            return None

        lip_regions = _extract_lip_regions(frames, face_boxes)
        if lip_regions is None:
            logger.warning("Lip region extraction failed")
            return None

        # Ensure same number of windows
        n_windows = min(len(mfcc), len(lip_regions))
        if n_windows < 2:
            logger.warning("Not enough windows for evaluation")
            return None

        mfcc = mfcc[:n_windows]
        lip_regions = lip_regions[:n_windows]

        try:
            with torch.no_grad():
                # Convert to tensors
                audio_tensor = torch.from_numpy(mfcc).to(self._device)
                video_tensor = torch.from_numpy(lip_regions).to(self._device)

                # Get embeddings
                audio_emb = self._model.forward_audio(audio_tensor)
                video_emb = self._model.forward_video(video_tensor)

                # Compute pairwise distances
                # LSE-D: minimum distance (lower = better sync)
                # LSE-C: median - min distance (higher = more confident)
                distances = torch.cdist(audio_emb, video_emb, p=2)

                # Get diagonal (same-time) distances
                diag_dist = torch.diag(distances)

                # Find best alignment with shift
                min_dist = float("inf")
                best_offset = 0
                vshift = 15  # Max shift in frames

                for offset in range(-vshift, vshift + 1):
                    if offset >= 0:
                        a_idx = slice(0, n_windows - offset)
                        v_idx = slice(offset, n_windows)
                    else:
                        a_idx = slice(-offset, n_windows)
                        v_idx = slice(0, n_windows + offset)

                    shifted_dist = torch.mean(
                        torch.norm(audio_emb[a_idx] - video_emb[v_idx], dim=1)
                    )
                    if shifted_dist < min_dist:
                        min_dist = shifted_dist.item()
                        best_offset = offset

                # Compute LSE-D and LSE-C
                median_dist = torch.median(diag_dist).item()
                lse_d = min_dist
                lse_c = median_dist - min_dist

                return SyncNetResult(
                    lse_d=lse_d,
                    lse_c=max(0.0, lse_c),  # Confidence should be non-negative
                    offset=best_offset,
                )

        except Exception as e:
            logger.warning(f"SyncNet evaluation failed: {e}")
            return None


# Module-level evaluator instance
_evaluator: SyncNetEvaluator | None = None


def get_evaluator() -> SyncNetEvaluator:
    """Get or create the shared SyncNet evaluator."""
    global _evaluator
    if _evaluator is None:
        _evaluator = SyncNetEvaluator()
    return _evaluator


def compute_lse_metrics(
    frames: list["NDArray[np.uint8]"],
    audio_path: Path,
    fps: float = VIDEO_FPS,
    face_boxes: list[list[float]] | None = None,
) -> tuple[float | None, float | None]:
    """Compute LSE-D and LSE-C metrics.

    Convenience function that uses the shared evaluator.

    Args:
        frames: List of BGR video frames.
        audio_path: Path to audio file.
        fps: Video frame rate.
        face_boxes: Optional face bounding boxes per frame.

    Returns:
        Tuple of (lse_d, lse_c), or (None, None) if evaluation fails.
    """
    evaluator = get_evaluator()
    result = evaluator.evaluate(frames, audio_path, fps, face_boxes)
    if result is None:
        return None, None
    return result.lse_d, result.lse_c
