"""Optional OS mouse playback of planned trajectories (lab / offline only)."""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from cv_agent.timing.step import step_delay
from cv_agent.trajectory.paths import Trajectory, generate, smoothness_features


MOUSEEVENTF_MOVE = 0x0001
ULONG_PTR = getattr(wintypes, "ULONG_PTR", ctypes.c_size_t)


def _send_relative(dx: int, dy: int) -> None:
    if sys.platform != "win32" or (dx == 0 and dy == 0):
        return
    extra = ULONG_PTR(0)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = (
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        )

    class INPUT(ctypes.Structure):
        _fields_ = (("type", wintypes.DWORD), ("mi", MOUSEINPUT))

    inp = INPUT()
    inp.type = 0
    inp.mi = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, extra)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


class AimController:
    """Plan (ΔX, ΔY) → trajectory; optionally play as relative mouse moves."""

    def __init__(self) -> None:
        self._fractional_x = 0.0
        self._fractional_y = 0.0

    def reset(self) -> None:
        self._fractional_x = 0.0
        self._fractional_y = 0.0

    def apply_correction(self, dx: float, dy: float, *, max_step: float = 24.0, deadzone: float = 0.5) -> dict[str, float]:
        """Send one bounded relative correction for a realtime frame."""
        import math
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
        _send_relative(sx, sy)
        return {"sent_dx": float(sx), "sent_dy": float(sy), "remaining_error": distance}

    def plan(self, dx: float, dy: float, algorithm: str = "linear", **kwargs) -> Trajectory:
        return generate(algorithm, dx, dy, **kwargs)

    def execute(
        self,
        traj: Trajectory,
        *,
        apply_mouse: bool = False,
        delay_s: float | None = None,
    ) -> dict[str, float]:
        features = smoothness_features(traj)
        if not apply_mouse:
            return features
        for ddx, ddy in traj.deltas:
            _send_relative(int(round(ddx)), int(round(ddy)))
            time.sleep(step_delay(delay_s))
        return features
