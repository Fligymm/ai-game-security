"""Backend-neutral controller for planning and relative movement output."""

from __future__ import annotations

import math
import time
from typing import Mapping

from cv_agent.control.base import BaseMouseBackend
from cv_agent.control.backends.csv_logger import CSVLoggerBackend
from cv_agent.timing.step import step_delay
from cv_agent.trajectory.paths import Trajectory, generate, smoothness_features


class AimController:
    """Plan trajectories and send them to an injected output strategy."""

    def __init__(self, backend: BaseMouseBackend | None = None) -> None:
        self.backend = backend if backend is not None else CSVLoggerBackend("runs/predict/control_moves.csv")
        self._fractional_x = 0.0
        self._fractional_y = 0.0

    def reset(self) -> None:
        self._fractional_x = 0.0
        self._fractional_y = 0.0
        self.backend.reset()

    def close(self) -> None:
        self.backend.close()

    def set_output_context(self, values: Mapping[str, object] | None = None) -> None:
        self.backend.set_context(values)

    def apply_correction(self, dx: float, dy: float, *, max_step: float = 24.0, deadzone: float = 0.5) -> dict[str, float]:
        distance = math.hypot(float(dx), float(dy))
        if distance <= float(deadzone):
            self.reset()
            return {"sent_dx": 0.0, "sent_dy": 0.0, "remaining_error": distance}
        scale = min(1.0, float(max_step) / max(distance, 1e-9))
        self._fractional_x += float(dx) * scale
        self._fractional_y += float(dy) * scale
        sx, sy = int(round(self._fractional_x)), int(round(self._fractional_y))
        self._fractional_x -= sx
        self._fractional_y -= sy
        self.backend.send_relative_move(sx, sy)
        return {"sent_dx": float(sx), "sent_dy": float(sy), "remaining_error": distance}

    def plan(self, dx: float, dy: float, algorithm: str = "linear", **kwargs) -> Trajectory:
        return generate(algorithm, dx, dy, **kwargs)

    def execute(self, traj: Trajectory, *, apply_mouse: bool = False, delay_s: float | None = None) -> dict[str, float]:
        features = smoothness_features(traj)
        self.set_output_context(traj.extras)
        if not apply_mouse:
            return features
        for ddx, ddy in traj.deltas:
            self.backend.send_relative_move(int(round(ddx)), int(round(ddy)))
            time.sleep(step_delay(delay_s))
        return features
