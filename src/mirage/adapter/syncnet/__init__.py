"""SyncNet adapter for lip-sync evaluation.

Provides LSE-D (Lip Sync Error Distance) and LSE-C (Lip Sync Error Confidence)
metrics using the SyncNet model for audio-visual synchronization assessment.

Model weights are downloaded automatically on first use.
Gracefully returns None when dependencies are unavailable.
"""

from mirage.adapter.syncnet.syncnet_adapter import SyncNetEvaluator, compute_lse_metrics

__all__ = ["SyncNetEvaluator", "compute_lse_metrics"]
