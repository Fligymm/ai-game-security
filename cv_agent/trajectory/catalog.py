"""Trajectory catalog and analysis labels for short-term movement testing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TrajectoryFamily = Literal[
    "snap",
    "interpolated",
    "ease_out",
    "curved",
    "feedback_control",
    "stochastic",
]


@dataclass(frozen=True)
class TrajectoryProfile:
    name: str
    family: TrajectoryFamily
    description: str
    deterministic: bool
    closed_loop: bool
    curvature: str
    anticheat_signal: tuple[str, ...]
    tags: tuple[str, ...] = ()


TRAJECTORY_PROFILES: dict[str, TrajectoryProfile] = {
    "direct": TrajectoryProfile(
        name="direct",
        family="snap",
        description="Single-step residual lock with maximal jerk.",
        deterministic=True,
        closed_loop=False,
        curvature="none",
        anticheat_signal=("single_step", "high_jerk", "minimal_smoothing"),
        tags=("snap", "baseline", "lock_signature"),
    ),
    "linear": TrajectoryProfile(
        name="linear",
        family="interpolated",
        description="Uniform interpolation with constant per-step displacement.",
        deterministic=True,
        closed_loop=False,
        curvature="none",
        anticheat_signal=("constant_speed", "low_variance", "uniform_spacing"),
        tags=("baseline", "interpolated", "constant_speed"),
    ),
    "exponential": TrajectoryProfile(
        name="exponential",
        family="ease_out",
        description="Decaying step size as residual shrinks.",
        deterministic=True,
        closed_loop=False,
        curvature="low",
        anticheat_signal=("ease_out", "deceleration", "step_decay"),
        tags=("smooth", "decelerating", "residual_decay"),
    ),
    "bezier": TrajectoryProfile(
        name="bezier",
        family="curved",
        description="Seeded cubic Bezier with lateral bow and visible curvature.",
        deterministic=True,
        closed_loop=False,
        curvature="medium",
        anticheat_signal=("curved_path", "seeded_shape", "mid_path_bow"),
        tags=("curved", "seeded", "synthetic"),
    ),
    "pid": TrajectoryProfile(
        name="pid",
        family="feedback_control",
        description="Closed-loop discrete PID on target residual.",
        deterministic=True,
        closed_loop=True,
        curvature="adaptive",
        anticheat_signal=("feedback_loop", "error_correction", "adaptive_response"),
        tags=("closed_loop", "controller", "adaptive"),
    ),
    "windmouse": TrajectoryProfile(
        name="windmouse",
        family="stochastic",
        description="Gravity-plus-wind motion model with injected randomness.",
        deterministic=False,
        closed_loop=False,
        curvature="variable",
        anticheat_signal=("randomized_steps", "noise_injection", "jerk_variance"),
        tags=("stochastic", "bot-research", "noise"),
    ),
}


def get_trajectory_profile(name: str) -> TrajectoryProfile:
    key = name.lower().strip()
    if key not in TRAJECTORY_PROFILES:
        raise ValueError(f"unknown trajectory '{name}', expected {sorted(TRAJECTORY_PROFILES)}")
    return TRAJECTORY_PROFILES[key]


def classify_trajectory(name: str) -> TrajectoryFamily:
    return get_trajectory_profile(name).family


def trajectory_catalog() -> list[TrajectoryProfile]:
    return [TRAJECTORY_PROFILES[name] for name in sorted(TRAJECTORY_PROFILES)]


def trajectory_groups() -> dict[TrajectoryFamily, list[str]]:
    groups: dict[TrajectoryFamily, list[str]] = {}
    for profile in trajectory_catalog():
        groups.setdefault(profile.family, []).append(profile.name)
    return groups