"""Pixel-offset trajectories for lab simulation and later anticheat features.

Each generator maps a residual (ΔX, ΔY) to a path starting at (0, 0).
Paths are recorded as time series for smoothness / aim-assist analysis.
They do not call YOLODetector or change detection class ids.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Trajectory:
    name: str
    points: list[tuple[float, float]]
    extras: dict[str, float] = field(default_factory=dict)

    @property
    def deltas(self) -> list[tuple[float, float]]:
        pts = self.points
        if len(pts) < 2:
            return []
        out = []
        for i in range(1, len(pts)):
            out.append((pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
        return out

    @property
    def speeds(self) -> list[float]:
        return [float(np.hypot(dx, dy)) for dx, dy in self.deltas]


def _close(points: list[tuple[float, float]], dx: float, dy: float) -> list[tuple[float, float]]:
    if not points:
        return [(dx, dy)]
    if abs(points[-1][0] - dx) > 1e-6 or abs(points[-1][1] - dy) > 1e-6:
        points.append((float(dx), float(dy)))
    return points


def direct(dx: float, dy: float) -> Trajectory:
    """Instant snap: one step to the residual (classic 'lock' signature)."""
    return Trajectory("direct", [(0.0, 0.0), (float(dx), float(dy))])


def linear(dx: float, dy: float, steps: int = 12) -> Trajectory:
    """Constant-speed linear interpolation (uniform Δ per step)."""
    steps = max(int(steps), 1)
    pts = [
        ((i / steps) * dx, (i / steps) * dy) for i in range(steps + 1)
    ]
    return Trajectory("linear", pts)


def exponential(dx: float, dy: float, alpha: float = 0.25, min_step: float = 0.5) -> Trajectory:
    """Exponential approach: remaining *= (1-alpha). Common in smooth aim."""
    alpha = float(np.clip(alpha, 0.01, 0.99))
    x = y = 0.0
    pts = [(0.0, 0.0)]
    for _ in range(200):
        rx, ry = dx - x, dy - y
        if np.hypot(rx, ry) < min_step:
            break
        x += alpha * rx
        y += alpha * ry
        pts.append((x, y))
    return Trajectory("exponential", _close(pts, dx, dy), {"alpha": alpha})


def bezier(dx: float, dy: float, steps: int = 20, bow: float = 0.35, seed: int = 0) -> Trajectory:
    """Cubic Bezier with a lateral bow (curved, still deterministic given seed)."""
    rng = np.random.default_rng(seed)
    steps = max(int(steps), 2)
    dist = max(float(np.hypot(dx, dy)), 1.0)
    nx, ny = -dy / dist, dx / dist
    side = 1.0 if rng.random() < 0.5 else -1.0
    mag = bow * dist * (0.6 + 0.8 * rng.random())
    p0 = np.array([0.0, 0.0])
    p3 = np.array([dx, dy])
    p1 = p0 + 0.33 * (p3 - p0) + side * mag * np.array([nx, ny])
    p2 = p0 + 0.66 * (p3 - p0) + side * 0.5 * mag * np.array([nx, ny])
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        p = (u**3) * p0 + 3 * (u**2) * t * p1 + 3 * u * (t**2) * p2 + (t**3) * p3
        pts.append((float(p[0]), float(p[1])))
    return Trajectory("bezier", pts, {"bow": bow})


def pid(
    dx: float,
    dy: float,
    kp: float = 0.35,
    ki: float = 0.02,
    kd: float = 0.08,
    steps: int = 24,
) -> Trajectory:
    """Discrete PID on residual; integral wind-up clamped."""
    x = y = 0.0
    ix = iy = 0.0
    px, py = dx, dy
    pts = [(0.0, 0.0)]
    for _ in range(max(int(steps), 1)):
        ex, ey = dx - x, dy - y
        ix = float(np.clip(ix + ex, -50.0, 50.0))
        iy = float(np.clip(iy + ey, -50.0, 50.0))
        dex, dey = ex - px, ey - py
        x += kp * ex + ki * ix + kd * dex
        y += kp * ey + ki * iy + kd * dey
        px, py = ex, ey
        pts.append((x, y))
        if np.hypot(dx - x, dy - y) < 0.5:
            break
    return Trajectory("pid", _close(pts, dx, dy), {"kp": kp, "ki": ki, "kd": kd})


def windmouse(
    dx: float,
    dy: float,
    gravity: float = 9.0,
    wind: float = 3.0,
    max_step: float = 15.0,
    dist_threshold: float = 12.0,
    seed: int = 0,
) -> Trajectory:
    """WindMouse (Ben Land): gravity toward target + decaying wind noise.

    Widely used in bot-research corpora; the resulting jerk/curvature
    statistics are useful anti-cheat features versus linear/PID.
    """
    rng = np.random.default_rng(seed)
    x = y = 0.0
    vx = vy = wx = wy = 0.0
    dest_x, dest_y = float(dx), float(dy)
    step_cap = float(max_step)
    pts = [(0.0, 0.0)]
    for _ in range(250):
        dist = float(np.hypot(dest_x - x, dest_y - y))
        if dist < 1.0:
            break
        wmag = min(wind, dist)
        if dist >= dist_threshold:
            wx = wx / np.sqrt(3) + (2 * rng.random() - 1) * wmag
            wy = wy / np.sqrt(3) + (2 * rng.random() - 1) * wmag
        else:
            wx /= np.sqrt(3)
            wy /= np.sqrt(3)
            step_cap = 3.0 + 3.0 * rng.random() if step_cap < 3.0 else step_cap / np.sqrt(5)
        vx += wx + gravity * (dest_x - x) / dist
        vy += wy + gravity * (dest_y - y) / dist
        v = float(np.hypot(vx, vy))
        if v > step_cap and v > 1e-9:
            clip = step_cap / 2.0 + rng.random() * step_cap / 2.0
            vx = vx / v * clip
            vy = vy / v * clip
        x += vx
        y += vy
        pts.append((x, y))
    return Trajectory("windmouse", _close(pts, dest_x, dest_y))


GENERATORS = {
    "direct": lambda dx, dy, **k: direct(dx, dy),
    "linear": lambda dx, dy, **k: linear(dx, dy, steps=int(k.get("steps", 12))),
    "exponential": lambda dx, dy, **k: exponential(
        dx, dy, alpha=float(k.get("alpha", 0.25))
    ),
    "bezier": lambda dx, dy, **k: bezier(
        dx, dy, steps=int(k.get("steps", 20)), seed=int(k.get("seed", 0))
    ),
    "pid": lambda dx, dy, **k: pid(dx, dy),
    "windmouse": lambda dx, dy, **k: windmouse(dx, dy, seed=int(k.get("seed", 0))),
}


def generate(name: str, dx: float, dy: float, **kwargs) -> Trajectory:
    key = name.lower().strip()
    if key not in GENERATORS:
        raise ValueError(f"unknown trajectory '{name}', expected {sorted(GENERATORS)}")
    return GENERATORS[key](dx, dy, **kwargs)


def smoothness_features(traj: Trajectory) -> dict[str, float]:
    """Cheap time-series stats for later anticheat models."""
    dxy = traj.deltas
    speeds = np.array(traj.speeds, dtype=np.float64)
    pts = np.array(traj.points, dtype=np.float64)
    if len(pts) < 2:
        return {"n_steps": float(len(dxy)), "path_len": 0.0, "jerk_mean": 0.0}
    segs = np.diff(pts, axis=0)
    path_len = float(np.sum(np.linalg.norm(segs, axis=1)))
    chord = float(np.hypot(pts[-1, 0] - pts[0, 0], pts[-1, 1] - pts[0, 1]))
    acc = np.diff(speeds)
    jerk = np.diff(acc) if len(acc) > 1 else np.array([0.0])
    speed_std = float(np.std(speeds)) if len(speeds) > 0 else 0.0
    jerk_mean = float(np.mean(np.abs(jerk))) if len(jerk) > 0 else 0.0
    return {
        "n_steps": float(len(dxy)),
        "path_len": path_len,
        "straightness": chord / max(path_len, 1e-6),
        "speed_std": speed_std,
        "jerk_mean": jerk_mean,
    }
