"""Constant-velocity Kalman filter on (ΔX, ΔY) for occlusion / miss handling."""

from __future__ import annotations

import numpy as np


class Kalman2D:
    """State ``[x, y, vx, vy]``, measurement ``[x, y]`` (pixel offsets)."""

    def __init__(
        self,
        process_var: float = 8.0,
        measure_var: float = 25.0,
        dt: float = 1.0,
    ) -> None:
        self.dt = float(dt)
        self.x = np.zeros((4, 1), dtype=np.float64)
        dt_ = self.dt
        self.F = np.array(
            [
                [1, 0, dt_, 0],
                [0, 1, 0, dt_],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ],
            dtype=np.float64,
        )
        self.H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float64)
        q = float(process_var)
        self.Q = np.diag([q, q, q, q]).astype(np.float64)
        r = float(measure_var)
        self.R = np.diag([r, r]).astype(np.float64)
        self.P = np.eye(4, dtype=np.float64) * 100.0
        self.initialized = False

    def predict(self) -> tuple[float, float]:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return float(self.x[0, 0]), float(self.x[1, 0])

    def update(self, zx: float, zy: float) -> tuple[float, float]:
        z = np.array([[zx], [zy]], dtype=np.float64)
        if not self.initialized:
            self.x[0, 0] = zx
            self.x[1, 0] = zy
            self.initialized = True
            return zx, zy
        y = z - self.H @ self.x
        s = self.H @ self.P @ self.H.T + self.R
        k = self.P @ self.H.T @ np.linalg.inv(s)
        self.x = self.x + k @ y
        i = np.eye(4)
        self.P = (i - k @ self.H) @ self.P
        return float(self.x[0, 0]), float(self.x[1, 0])

    def predict_then_update(self, zx: float, zy: float) -> tuple[float, float]:
        self.predict()
        return self.update(zx, zy)
