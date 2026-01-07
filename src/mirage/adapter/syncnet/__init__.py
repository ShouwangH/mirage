"""Lip-sync evaluation adapter.

Provides LSE-D (Lip Sync Error Distance) and LSE-C (Lip Sync Error Confidence)
metrics using correlation between mouth movement and audio energy.

- LSE-D: Lower is better (< 8 is good)
- LSE-C: Higher is better (> 3 is good)
"""

from mirage.adapter.syncnet.syncnet_adapter import SyncNetEvaluator, compute_lse_metrics

__all__ = ["SyncNetEvaluator", "compute_lse_metrics"]
