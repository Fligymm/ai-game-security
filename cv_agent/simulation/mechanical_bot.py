"""Deterministic mechanical bot baseline for offline detector evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path

import numpy as np

from cv_agent.analytics.trajectory_schema import EventSegment, TrajectorySession


@dataclass(frozen=True, slots=True)
class MechanicalBotTrajectory:
    session: TrajectorySession

    def save_json(self, path: str | Path) -> Path:
        output = Path(path)
        os.makedirs(os.path.dirname(os.fspath(output)) or ".", exist_ok=True)
        output.write_text(json.dumps(self.session.to_dict(), indent=2), encoding="utf-8")
        print(f"[INFO] Successfully generated {self.session.frame_count} mechanical samples to {output}")
        return output


class MechanicalBotAgent:
    """Generate straight, constant-speed trajectories without stochastic behavior."""

    def __init__(self, *, speed_px_s: float = 1500.0, sample_rate_hz: float = 120.0, target_size_px: float = 20.0) -> None:
        if speed_px_s <= 0 or sample_rate_hz <= 0 or target_size_px < 0:
            raise ValueError("speed and sample rate must be positive; target size must be non-negative")
        self.speed_px_s = float(speed_px_s)
        self.sample_rate_hz = float(sample_rate_hz)
        self.target_size_px = float(target_size_px)

    def generate(
        self,
        start: tuple[float, float],
        target: tuple[float, float],
        *,
        session_id: str,
        seed: int | None = None,
    ) -> MechanicalBotTrajectory:
        del seed  # Kept for API compatibility; this baseline is deterministic.
        start_point = np.asarray(start, dtype=np.float64)
        target_point = np.asarray(target, dtype=np.float64)
        vector = target_point - start_point
        distance = float(np.linalg.norm(vector))
        if distance == 0.0:
            positions = np.vstack((start_point, target_point))
            timestamps = [0.0, 1.0 / self.sample_rate_hz]
        else:
            duration = distance / self.speed_px_s
            steps = max(1, int(np.ceil(duration * self.sample_rate_hz)))
            timestamps = np.linspace(0.0, duration, steps + 1).tolist()
            positions = start_point + np.linspace(0.0, 1.0, steps + 1)[:, None] * vector
        deltas = np.diff(positions, axis=0)
        dx = [0] + [int(round(value)) for value in deltas[:, 0]]
        dy = [0] + [int(round(value)) for value in deltas[:, 1]]
        session = TrajectorySession(
            session_id=session_id,
            source="bot_agent",
            target_distance_px=distance,
            target_size_px=self.target_size_px,
            reaction_time_ms=0.0,
            timestamps=[float(value) for value in timestamps],
            x=[float(value) for value in positions[:, 0]],
            y=[float(value) for value in positions[:, 1]],
            dx=dx,
            dy=dy,
            event_segments=[EventSegment("coarse_move", 0, len(timestamps))],
            seed=None,
        )
        return MechanicalBotTrajectory(session=session)


__all__ = ["MechanicalBotAgent", "MechanicalBotTrajectory"]
