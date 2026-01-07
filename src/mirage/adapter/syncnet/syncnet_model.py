"""SyncNet model architecture.

Based on the original SyncNet from:
"Out of time: automated lip sync in the wild" (Chung & Zisserman, 2016)
https://github.com/joonson/syncnet_python

This is a dual-stream network that produces embeddings for both
audio (MFCC) and video (lip region) for synchronization scoring.
"""

from __future__ import annotations

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


def _check_torch() -> None:
    """Verify torch is available."""
    if not TORCH_AVAILABLE:
        raise ImportError(
            "PyTorch is required for SyncNet. "
            "Install with: pip install torch torchvision torchaudio"
        )


class SyncNetModel(nn.Module if TORCH_AVAILABLE else object):
    """SyncNet dual-stream architecture for audio-visual sync scoring.

    Audio stream: 1D CNN processing MFCC features
    Video stream: 3D CNN processing lip region frames

    Both produce 1024-dimensional embeddings for comparison.
    """

    def __init__(self) -> None:
        """Initialize SyncNet model."""
        _check_torch()
        super().__init__()

        # Audio stream (1D CNN on MFCC features)
        self.audio_encoder = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1)),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(1, 1), stride=(1, 1)),
            nn.Conv2d(64, 192, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1)),
            nn.BatchNorm2d(192),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(3, 3), stride=(1, 2)),
            nn.Conv2d(192, 384, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1)),
            nn.BatchNorm2d(384),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 256, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1)),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.Conv2d(256, 256, kernel_size=(3, 3), stride=(1, 1), padding=(1, 1)),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=(3, 3), stride=(2, 2)),
            nn.Conv2d(256, 512, kernel_size=(5, 4), stride=(1, 1), padding=(0, 0)),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
        )

        self.audio_fc = nn.Sequential(
            nn.Linear(512, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Linear(512, 1024),
        )

        # Video stream (3D CNN on lip region frames)
        self.video_encoder = nn.Sequential(
            nn.Conv3d(3, 96, kernel_size=(5, 7, 7), stride=(1, 2, 2), padding=0),
            nn.BatchNorm3d(96),
            nn.ReLU(inplace=True),
            nn.MaxPool3d(kernel_size=(1, 3, 3), stride=(1, 2, 2)),
            nn.Conv3d(96, 256, kernel_size=(1, 5, 5), stride=(1, 2, 2), padding=(0, 1, 1)),
            nn.BatchNorm3d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool3d(kernel_size=(1, 3, 3), stride=(1, 2, 2), padding=(0, 1, 1)),
            nn.Conv3d(256, 256, kernel_size=(1, 3, 3), stride=(1, 1, 1), padding=(0, 1, 1)),
            nn.BatchNorm3d(256),
            nn.ReLU(inplace=True),
            nn.Conv3d(256, 256, kernel_size=(1, 3, 3), stride=(1, 1, 1), padding=(0, 1, 1)),
            nn.BatchNorm3d(256),
            nn.ReLU(inplace=True),
            nn.Conv3d(256, 256, kernel_size=(1, 3, 3), stride=(1, 1, 1), padding=(0, 1, 1)),
            nn.BatchNorm3d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool3d(kernel_size=(1, 3, 3), stride=(1, 2, 2)),
            nn.Conv3d(256, 512, kernel_size=(1, 6, 6), stride=(1, 1, 1), padding=0),
            nn.BatchNorm3d(512),
            nn.ReLU(inplace=True),
        )

        self.video_fc = nn.Sequential(
            nn.Linear(512, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Linear(512, 1024),
        )

    def forward_audio(self, x: "torch.Tensor") -> "torch.Tensor":
        """Extract audio embedding from MFCC features.

        Args:
            x: Audio MFCC tensor of shape (B, 1, T, 13) where
               B=batch, T=time steps, 13=MFCC coefficients.

        Returns:
            Audio embedding of shape (B, 1024).
        """
        x = self.audio_encoder(x)
        x = x.view(x.size(0), -1)
        x = self.audio_fc(x)
        return x

    def forward_video(self, x: "torch.Tensor") -> "torch.Tensor":
        """Extract video embedding from lip region frames.

        Args:
            x: Video tensor of shape (B, 3, T, H, W) where
               B=batch, 3=RGB, T=time steps, H/W=height/width.

        Returns:
            Video embedding of shape (B, 1024).
        """
        x = self.video_encoder(x)
        x = x.view(x.size(0), -1)
        x = self.video_fc(x)
        return x

    def forward(
        self, audio: "torch.Tensor", video: "torch.Tensor"
    ) -> tuple["torch.Tensor", "torch.Tensor"]:
        """Forward pass producing both embeddings.

        Args:
            audio: MFCC features tensor.
            video: Lip region video tensor.

        Returns:
            Tuple of (audio_embedding, video_embedding).
        """
        return self.forward_audio(audio), self.forward_video(video)
