"""Inter-step delays for simulated or played-back aim paths."""

from __future__ import annotations


def step_delay(delay_s: float | None = None) -> float:
    """Seconds between trajectory samples (default ~8 ms ≈ 125 Hz poll)."""
    if delay_s is None:
        return 0.008
    return max(float(delay_s), 0.0)
