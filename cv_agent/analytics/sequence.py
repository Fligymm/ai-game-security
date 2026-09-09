"""Conversion of trajectory sessions to fixed-length neural-network sequences."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from .trajectory_schema import TrajectorySession


class TrajectorySequenceEncoder:
    """Encode trajectory steps as ``[dx, dy, speed, acceleration, angular_velocity, dt, offset_x, offset_y]``."""

    feature_dim = 8

    def __init__(self, max_len: int) -> None:
        if isinstance(max_len, bool) or max_len <= 0:
            raise ValueError("max_len must be a positive integer")
        self.max_len = int(max_len)

    def _session(self, value: TrajectorySession | dict[str, Any]) -> TrajectorySession:
        if isinstance(value, TrajectorySession):
            return value
        if isinstance(value, dict):
            return TrajectorySession.from_dict(value)
        raise TypeError("session must be a TrajectorySession or parsed JSON dictionary")

    def encode(self, session: TrajectorySession | dict[str, Any]) -> np.ndarray:
        data, _ = self.encode_with_mask(session)
        return data

    transform = encode

    def encode_with_mask(self, session: TrajectorySession | dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        trajectory = self._session(session)
        output = np.zeros((self.max_len, self.feature_dim), dtype=np.float32)
        mask = np.zeros(self.max_len, dtype=bool)
        n = min(trajectory.frame_count, self.max_len)
        if n == 0:
            return output, mask
        final_x, final_y = trajectory.x[-1], trajectory.y[-1]
        previous_speed = 0.0
        previous_angle: float | None = None
        for i in range(n):
            dt = trajectory.timestamps[i] - trajectory.timestamps[i - 1] if i else trajectory.timestamps[0]
            dt = max(float(dt), np.finfo(np.float32).eps)
            dx, dy = float(trajectory.dx[i]), float(trajectory.dy[i])
            speed = math.hypot(dx, dy) / dt
            acceleration = (speed - previous_speed) / dt if i else 0.0
            angle = math.atan2(dy, dx) if dx or dy else previous_angle
            angular_velocity = 0.0
            if angle is not None and previous_angle is not None:
                delta = (angle - previous_angle + math.pi) % (2 * math.pi) - math.pi
                angular_velocity = delta / dt
            output[i] = (dx, dy, speed, acceleration, angular_velocity, dt,
                         final_x - trajectory.x[i], final_y - trajectory.y[i])
            mask[i] = True
            previous_speed, previous_angle = speed, angle
        return output, mask

    def encode_with_padding_mask(self, session: TrajectorySession | dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        return self.encode_with_mask(session)


__all__ = ["TrajectorySequenceEncoder"]
