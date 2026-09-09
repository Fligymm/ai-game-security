"""Latency and control-quality metrics for Stage 2.3."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping, Sequence


class ControlPerformanceTracker:
    """Collect per-frame timings and movement samples, then summarize them."""

    _STAGES = ("grab", "inference", "selection", "control")

    def __init__(self) -> None:
        self._stage_latencies: dict[str, list[float]] = {stage: [] for stage in self._STAGES}
        self._total_latencies: list[float] = []
        self._grab_timestamps: list[float] = []
        self._errors: list[float] = []
        self._overshoot_ratios: list[float] = []
        self._overshoot_events = 0
        self._moves: list[tuple[float, float]] = []

    def record_latency(
        self,
        grab_time_ms: float,
        inference_time_ms: float,
        selection_time_ms: float,
        control_time_ms: float,
    ) -> None:
        """Record monotonic timestamps (milliseconds) for one processing frame."""
        values = tuple(float(v) for v in (grab_time_ms, inference_time_ms, selection_time_ms, control_time_ms))
        if not all(math.isfinite(v) for v in values):
            raise ValueError("timestamps must be finite numbers")
        if any(later < earlier for earlier, later in zip(values, values[1:])):
            raise ValueError("timestamps must be non-decreasing")
        self._grab_timestamps.append(values[0])
        durations = (0.0, values[1] - values[0], values[2] - values[1], values[3] - values[2])
        for stage, duration in zip(self._STAGES, durations):
            self._stage_latencies[stage].append(duration)
        self._total_latencies.append(values[3] - values[0])

    # Common integration aliases.
    record_frame = record_latency
    record_timestamps = record_latency
    record_timing = record_latency

    def record_step(
        self,
        target_center: Sequence[float],
        crosshair_pos: Sequence[float],
        dx: float,
        dy: float,
    ) -> None:
        """Record one control step and update error, overshoot, and jerk inputs."""
        if len(target_center) != 2 or len(crosshair_pos) != 2:
            raise ValueError("target_center and crosshair_pos must contain two values")
        target = (float(target_center[0]), float(target_center[1]))
        crosshair = (float(crosshair_pos[0]), float(crosshair_pos[1]))
        move = (float(dx), float(dy))
        if not all(math.isfinite(v) for v in (*target, *crosshair, *move)):
            raise ValueError("control values must be finite numbers")
        error_vector = (target[0] - crosshair[0], target[1] - crosshair[1])
        error = math.hypot(*error_vector)
        self._errors.append(error)
        if self._moves:
            previous_error = self._previous_error_vector
            # Crossing the target is represented by the error vector reversing direction.
            if previous_error[0] * error_vector[0] + previous_error[1] * error_vector[1] < 0:
                self._overshoot_events += 1
                before = math.hypot(*previous_error)
                self._overshoot_ratios.append(error / before if before > 0 else 0.0)
        self._previous_error_vector = error_vector
        self._moves.append(move)

    def latency_summary(self) -> dict[str, object]:
        """Return mean, P95, P99 and FPS for each latency stream."""
        result: dict[str, object] = {stage: self._stats(values) for stage, values in self._stage_latencies.items()}
        result["total"] = self._stats(self._total_latencies)
        result["fps"] = self._fps()
        result["frame_count"] = len(self._total_latencies)
        return result

    get_latency_stats = latency_summary

    def control_quality_summary(self) -> dict[str, float | int | bool]:
        steady_error = self._errors[-1] if self._errors else 0.0
        overshoot_ratio = (sum(self._overshoot_ratios) / len(self._overshoot_ratios)) if self._overshoot_ratios else 0.0
        return {
            "steady_state_error_px": steady_error,
            "steady_state_error": steady_error,
            "overshoot": self._overshoot_events > 0,
            "overshoot_events": self._overshoot_events,
            "overshoot_ratio": overshoot_ratio,
            "jerk_rms": self._jerk_rms(),
            "step_count": len(self._moves),
        }

    get_control_quality = control_quality_summary

    def summary(self) -> dict[str, object]:
        return {"latency": self.latency_summary(), "control_quality": self.control_quality_summary()}

    def export_summary_json(self, filepath: str | Path) -> Path:
        output = Path(filepath)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.summary(), indent=2), encoding="utf-8")
        return output

    @staticmethod
    def _stats(values: Sequence[float]) -> dict[str, float]:
        if not values:
            return {"mean_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0}
        ordered = sorted(values)
        return {"mean_ms": sum(ordered) / len(ordered), "p95_ms": ControlPerformanceTracker._percentile(ordered, 0.95), "p99_ms": ControlPerformanceTracker._percentile(ordered, 0.99)}

    @staticmethod
    def _percentile(ordered: Sequence[float], q: float) -> float:
        if not ordered:
            return 0.0
        index = (len(ordered) - 1) * q
        low, high = math.floor(index), math.ceil(index)
        return ordered[low] + (ordered[high] - ordered[low]) * (index - low)

    def _fps(self) -> float:
        if len(self._grab_timestamps) < 2:
            return 0.0
        elapsed_s = (self._grab_timestamps[-1] - self._grab_timestamps[0]) / 1000.0
        return (len(self._grab_timestamps) - 1) / elapsed_s if elapsed_s > 0 else 0.0

    def _jerk_rms(self) -> float:
        if len(self._moves) < 4:
            return 0.0
        jerks = []
        for i in range(3, len(self._moves)):
            jerk_x = self._moves[i][0] - 3 * self._moves[i - 1][0] + 3 * self._moves[i - 2][0] - self._moves[i - 3][0]
            jerk_y = self._moves[i][1] - 3 * self._moves[i - 1][1] + 3 * self._moves[i - 2][1] - self._moves[i - 3][1]
            jerks.append(math.hypot(jerk_x, jerk_y))
        return math.sqrt(sum(value * value for value in jerks) / len(jerks))


__all__ = ["ControlPerformanceTracker"]
