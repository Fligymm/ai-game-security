"""Optional OS mouse playback of planned trajectories (lab / offline only)."""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

from cv_agent.timing.step import step_delay
from cv_agent.trajectory.paths import Trajectory, generate, smoothness_features


MOUSEEVENTF_MOVE = 0x0001


def _send_relative(dx: int, dy: int) -> None:
    if sys.platform != "win32" or (dx == 0 and dy == 0):
        return
    extra = wintypes.ULONG_PTR(0)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = (
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.ULONG_PTR),
        )

    class INPUT(ctypes.Structure):
        _fields_ = (("type", wintypes.DWORD), ("mi", MOUSEINPUT))

    inp = INPUT()
    inp.type = 0
    inp.mi = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, extra)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


class AimController:
    """Plan (ΔX, ΔY) → trajectory; optionally play as relative mouse moves."""

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
