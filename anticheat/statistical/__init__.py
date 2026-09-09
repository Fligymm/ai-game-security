"""Distribution, outlier, and hypothesis-testing detectors."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


def evaluate_trajectory(
    points: Iterable[Sequence[float]],
    *,
    timestamps: Iterable[float] | None = None,
    sample_rate_hz: float = 125.0,
) -> dict[str, float | int | str]:
    """Compute kinematic and smoothness statistics for a mouse trajectory.

    ``points`` are absolute cursor positions or cumulative relative positions
    in ``(x, y)`` order. Jerk is the third finite difference of position,
    expressed in pixels/s^3 when timestamps/sample rate are supplied.
    ``machine_likeness`` is a screening heuristic, not a classifier.
    """
    xy = np.asarray(list(points), dtype=np.float64)
    if xy.size == 0:
        raise ValueError("trajectory must contain at least two points")
    if xy.ndim != 2 or xy.shape[1] != 2 or xy.shape[0] < 2:
        raise ValueError("trajectory must have shape (N, 2) with N >= 2")

    if timestamps is None:
        dt = np.full(xy.shape[0] - 1, 1.0 / max(float(sample_rate_hz), 1e-6))
    else:
        ts = np.asarray(list(timestamps), dtype=np.float64)
        if ts.shape != (xy.shape[0],):
            raise ValueError("timestamps must have the same length as points")
        dt = np.diff(ts)
        if np.any(dt <= 0):
            raise ValueError("timestamps must be strictly increasing")

    velocity = np.diff(xy, axis=0) / dt[:, None]
    speed = np.linalg.norm(velocity, axis=1)
    acceleration = np.diff(velocity, axis=0) / ((dt[1:] + dt[:-1]) / 2.0)[:, None] if len(velocity) >= 2 else np.empty((0, 2))
    jerk = np.diff(acceleration, axis=0) / ((dt[2:] + dt[1:-1]) / 2.0)[:, None] if len(acceleration) >= 2 else np.empty((0, 2))
    jerk_mag = np.linalg.norm(jerk, axis=1)

    displacement = float(np.linalg.norm(xy[-1] - xy[0]))
    path_length = float(np.sum(np.linalg.norm(np.diff(xy, axis=0), axis=1)))
    straightness = displacement / max(path_length, 1e-9)
    direction = np.diff(xy, axis=0)
    angles = np.arctan2(direction[:, 1], direction[:, 0])
    angle_delta = np.abs(np.arctan2(np.sin(np.diff(angles)), np.cos(np.diff(angles)))) if len(angles) >= 2 else np.empty(0)
    zero_fraction = float(np.mean(speed < 1.0))
    jerk_rms = float(np.sqrt(np.mean(jerk_mag**2))) if len(jerk_mag) else 0.0
    jerk_mean = float(np.mean(jerk_mag)) if len(jerk_mag) else 0.0
    speed_cv = float(np.std(speed) / max(np.mean(speed), 1e-9)) if len(speed) else 0.0
    smoothness = float(1.0 / (1.0 + jerk_rms / 1000.0))
    regularity = float(1.0 / (1.0 + speed_cv))
    machine_score = float(np.clip(0.45 * straightness + 0.35 * regularity + 0.20 * (1.0 - min(zero_fraction, 1.0)), 0.0, 1.0))

    return {
        "label": "screening_heuristic",
        "n_points": int(len(xy)),
        "path_length_px": path_length,
        "displacement_px": displacement,
        "straightness": float(straightness),
        "speed_mean_px_s": float(np.mean(speed)),
        "speed_std_px_s": float(np.std(speed)),
        "speed_cv": speed_cv,
        "acceleration_rms_px_s2": float(np.sqrt(np.mean(np.sum(acceleration**2, axis=1)))) if len(acceleration) else 0.0,
        "jerk_mean_px_s3": jerk_mean,
        "jerk_rms_px_s3": jerk_rms,
        "direction_change_mean_rad": float(np.mean(angle_delta)) if len(angle_delta) else 0.0,
        "zero_speed_fraction": zero_fraction,
        "smoothness_score": smoothness,
        "regularity_score": regularity,
        "machine_likeness_score": machine_score,
    }


def load_trajectory(path: str | Path) -> list[tuple[float, float]]:
    """Load points from JSON (list or {points: [...]}) or CSV with x,y columns."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        data = data.get("points", data) if isinstance(data, dict) else data
        return [(float(p[0]), float(p[1])) for p in data]
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [(float(row["x"]), float(row["y"])) for row in rows]


__all__ = ["evaluate_trajectory", "load_trajectory"]
