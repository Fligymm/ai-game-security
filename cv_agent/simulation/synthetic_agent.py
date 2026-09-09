"""Layered synthetic trajectories for offline anti-cheat evaluation data."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path

import numpy as np

from cv_agent.analytics.trajectory_schema import EventSegment, TrajectorySession


@dataclass(frozen=True, slots=True)
class SyntheticAgentConfig:
    """Sampling and timing controls for one synthetic session."""

    sample_rate_hz: float = 120.0
    reaction_mean_ms: float = 180.0
    reaction_std_ms: float = 25.0
    coarse_fraction: float = 0.78
    coarse_duration_s: float = 0.42
    correction_min: int = 0
    correction_max: int = 2
    target_size_px: float = 20.0
    feedback_scale_px: float = 1.5
    correction_scale_px: float = 3.0

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0 or self.reaction_mean_ms <= 0 or self.reaction_std_ms <= 0:
            raise ValueError("sampling rate and reaction distribution values must be positive")
        if not 0.0 < self.coarse_fraction < 1.0 or self.coarse_duration_s <= 0:
            raise ValueError("invalid coarse-move configuration")
        if self.correction_min < 0 or self.correction_max < self.correction_min:
            raise ValueError("invalid correction range")
        if self.target_size_px < 0 or self.feedback_scale_px < 0 or self.correction_scale_px < 0:
            raise ValueError("trajectory scales must be non-negative")


@dataclass(frozen=True, slots=True)
class SyntheticAgentTrajectory:
    """Generated session plus generation diagnostics."""

    session: TrajectorySession
    diagnostics: dict[str, float | int | bool]

    def save_json(self, path: str | Path) -> Path:
        output = Path(path)
        os.makedirs(os.path.dirname(os.fspath(output)) or ".", exist_ok=True)
        output.write_text(json.dumps(self.session.to_dict(), indent=2), encoding="utf-8")
        print(f"[INFO] Successfully generated {self.session.frame_count} samples to {output}")
        return output


class SyntheticAgent:
    """Generate labeled layered trajectories without any output backend."""

    def __init__(self, config: SyntheticAgentConfig | None = None) -> None:
        self.config = config if config is not None else SyntheticAgentConfig()

    def generate(
        self,
        start: tuple[float, float],
        target: tuple[float, float],
        *,
        session_id: str,
        seed: int | None = None,
    ) -> SyntheticAgentTrajectory:
        rng = np.random.default_rng(seed)
        cfg = self.config
        x0, y0 = map(float, start)
        xt, yt = map(float, target)
        vector = np.array([xt - x0, yt - y0], dtype=np.float64)
        distance = float(np.linalg.norm(vector))
        direction = vector / max(distance, np.finfo(float).eps)
        perpendicular = np.array([-direction[1], direction[0]])
        dt = 1.0 / cfg.sample_rate_hz

        points: list[tuple[float, float]] = []
        phase_ranges: dict[str, tuple[int, int]] = {}

        reaction_ms = self._sample_reaction_ms(
            rng,
            mean_ms=cfg.reaction_mean_ms,
            std_ms=cfg.reaction_std_ms,
        )
        reaction_count = max(1, int(np.ceil(reaction_ms / 1000.0 * cfg.sample_rate_hz)))
        phase_ranges["reaction_phase"] = (0, reaction_count)
        points.extend([(x0, y0)] * reaction_count)

        coarse_count = max(2, int(round(cfg.coarse_duration_s * cfg.sample_rate_hz)))
        coarse_start = len(points)
        peak_fraction = float(np.clip(rng.beta(2.5, 5.0), 0.30, 0.70))
        coarse_end_point = np.array([x0, y0]) + vector * cfg.coarse_fraction
        for index in range(1, coarse_count + 1):
            u = index / coarse_count
            warped = self._asymmetric_progress(u, peak_fraction)
            progress = self._minimum_jerk(warped)
            point = np.array([x0, y0]) + (coarse_end_point - np.array([x0, y0])) * progress
            points.append((float(point[0]), float(point[1])))
        phase_ranges["coarse_move"] = (coarse_start, len(points))

        decel_start = len(points)
        decel_count = max(3, int(round(0.16 * cfg.sample_rate_hz)))
        low_frequency_bias = rng.normal(0.0, cfg.feedback_scale_px, 2)
        for index in range(1, decel_count + 1):
            u = index / decel_count
            progress = self._minimum_jerk(u)
            bias = low_frequency_bias * np.sin(np.pi * u) ** 0.8
            point = coarse_end_point + (vector * (1.0 - cfg.coarse_fraction) + bias) * progress
            points.append((float(point[0]), float(point[1])))
        phase_ranges["deceleration"] = (decel_start, len(points))

        correction_count = int(
            np.clip(
                rng.poisson(min(1.0 + distance / 500.0, float(cfg.correction_max))),
                cfg.correction_min,
                cfg.correction_max,
            )
        )
        correction_ranges: list[tuple[int, int]] = []
        for correction_index in range(correction_count):
            correction_start = len(points)
            magnitude = cfg.correction_scale_px * (0.75 ** correction_index)
            sign = -1.0 if correction_index % 2 else 1.0
            offset = perpendicular * sign * magnitude + direction * rng.normal(0.0, magnitude * 0.25)
            waypoint = np.array([xt, yt]) + offset
            current = np.array(points[-1])
            correction_steps = max(3, int(round((0.07 + 0.02 * correction_index) * cfg.sample_rate_hz)))
            for index in range(1, correction_steps + 1):
                u = index / correction_steps
                decay = np.exp(-4.0 * u)
                point = np.array([xt, yt]) + offset * decay
                if index == 1:
                    point = current + (waypoint - current) * min(1.0, u * 2.0)
                points.append((float(point[0]), float(point[1])))
            correction_ranges.append((correction_start, len(points)))

        if not points or points[-1] != (xt, yt):
            points.append((xt, yt))

        timestamps = [index * dt for index in range(len(points))]
        positions = np.asarray(points, dtype=np.float64)
        deltas = np.diff(positions, axis=0)
        dx = [int(round(value)) for value in deltas[:, 0]]
        dy = [int(round(value)) for value in deltas[:, 1]]
        dx.insert(0, 0)
        dy.insert(0, 0)
        event_segments = [EventSegment("reaction_phase", *phase_ranges["reaction_phase"])]
        event_segments.append(EventSegment("coarse_move", *phase_ranges["coarse_move"]))
        event_segments.append(EventSegment("deceleration", *phase_ranges["deceleration"]))
        event_segments.extend(EventSegment("micro_correction", start, end) for start, end in correction_ranges)

        session = TrajectorySession(
            session_id=session_id,
            source="synthetic_adversarial",
            target_distance_px=distance,
            target_size_px=cfg.target_size_px,
            reaction_time_ms=reaction_ms,
            timestamps=timestamps,
            x=[float(value) for value in positions[:, 0]],
            y=[float(value) for value in positions[:, 1]],
            dx=dx,
            dy=dy,
            event_segments=event_segments,
            seed=seed,
        )
        diagnostics: dict[str, float | int | bool] = {
            "reaction_samples": reaction_count,
            "peak_fraction": peak_fraction,
            "correction_count": correction_count,
            "overshoot_like_correction": bool(correction_count > 0),
        }
        return SyntheticAgentTrajectory(session=session, diagnostics=diagnostics)

    @staticmethod
    def _minimum_jerk(progress: float) -> float:
        value = float(np.clip(progress, 0.0, 1.0))
        return 10.0 * value**3 - 15.0 * value**4 + 6.0 * value**5

    @staticmethod
    def _asymmetric_progress(progress: float, peak_fraction: float) -> float:
        if progress <= peak_fraction:
            return 0.5 * progress / max(peak_fraction, np.finfo(float).eps)
        return 0.5 + 0.5 * (progress - peak_fraction) / max(1.0 - peak_fraction, np.finfo(float).eps)

    @staticmethod
    def _sample_reaction_ms(rng: np.random.Generator, mean_ms: float = 180.0, std_ms: float = 25.0) -> float:
        sigma2 = np.log(1.0 + (std_ms / mean_ms) ** 2)
        sigma = float(np.sqrt(sigma2))
        mu = float(np.log(mean_ms) - sigma2 / 2.0)
        return float(max(1.0, rng.lognormal(mu, sigma)))


__all__ = ["SyntheticAgent", "SyntheticAgentConfig", "SyntheticAgentTrajectory"]
