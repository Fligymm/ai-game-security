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
    reaction_pause_log_mu: float = 5.3
    reaction_pause_log_sigma: float = 0.25
    post_click_pause_log_mu: float = 4.5
    post_click_pause_log_sigma: float = 0.3
    coarse_fraction: float = 0.78
    coarse_duration_s: float = 0.58
    correction_min: int = 0
    correction_max: int = 2
    target_size_px: float = 20.0
    feedback_scale_px: float = 1.5
    correction_scale_px: float = 3.0
    tremor_probability: float = 0.7
    tremor_scale_px: float = 0.18

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0 or self.reaction_mean_ms <= 0 or self.reaction_std_ms <= 0:
            raise ValueError("sampling rate and reaction distribution values must be positive")
        if self.reaction_pause_log_sigma <= 0 or self.post_click_pause_log_sigma <= 0:
            raise ValueError("log-normal pause scales must be positive")
        if not 0.0 < self.coarse_fraction < 1.0 or self.coarse_duration_s <= 0:
            raise ValueError("invalid coarse-move configuration")
        if self.correction_min < 0 or self.correction_max < self.correction_min:
            raise ValueError("invalid correction range")
        if self.target_size_px < 0 or self.feedback_scale_px < 0 or self.correction_scale_px < 0:
            raise ValueError("trajectory scales must be non-negative")
        if not 0.0 <= self.tremor_probability <= 1.0 or self.tremor_scale_px < 0:
            raise ValueError("tremor controls must be within valid bounds")


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

        reaction_ms = self._sample_lognormal_ms(
            rng,
            mu=cfg.reaction_pause_log_mu,
            sigma=cfg.reaction_pause_log_sigma,
            lower_ms=160.0,
            upper_ms=250.0,
        )
        reaction_count = max(1, int(np.round(reaction_ms / 1000.0 * cfg.sample_rate_hz)))
        phase_ranges["reaction_phase"] = (0, reaction_count)
        points.extend([(x0, y0)] * reaction_count)

        coarse_count = max(2, int(round(cfg.coarse_duration_s * cfg.sample_rate_hz)))
        coarse_start = len(points)
        peak_fraction = float(np.clip(rng.beta(2.5, 5.0), 0.30, 0.70))
        coarse_end_point = np.array([x0, y0]) + vector * cfg.coarse_fraction
        tremor_profile = self._make_tremor_profile(
            rng,
            count=coarse_count,
            scale_px=min(cfg.tremor_scale_px + 0.0015 * distance, 0.45),
            enabled=distance > 32.0 and rng.random() < cfg.tremor_probability,
        )
        for index in range(1, coarse_count + 1):
            u = index / coarse_count
            warped = self._asymmetric_progress(u, peak_fraction)
            progress = self._minimum_jerk(warped)
            point = np.array([x0, y0]) + (coarse_end_point - np.array([x0, y0])) * progress
            point = point + perpendicular * tremor_profile[index - 1]
            points.append((float(point[0]), float(point[1])))
        phase_ranges["coarse_move"] = (coarse_start, len(points))

        decel_start = len(points)
        decel_count = max(3, int(round(0.16 * cfg.sample_rate_hz)))
        low_frequency_bias = rng.normal(0.0, cfg.feedback_scale_px, 2)
        for index in range(1, decel_count + 1):
            u = index / decel_count
            progress = self._minimum_jerk(u)
            bias = low_frequency_bias * np.sin(np.pi * u) ** 1.4 * self._minimum_jerk(u)
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
            out_steps = max(3, int(round((0.035 + 0.01 * correction_index) * cfg.sample_rate_hz)))
            return_steps = max(3, int(round((0.045 + 0.01 * correction_index) * cfg.sample_rate_hz)))
            points.extend(self._quintic_segment(current, waypoint, out_steps))
            points.extend(self._quintic_segment(waypoint, np.array([xt, yt]), return_steps))
            correction_ranges.append((correction_start, len(points)))

        post_pause_ms = self._sample_lognormal_ms(
            rng,
            mu=cfg.post_click_pause_log_mu,
            sigma=cfg.post_click_pause_log_sigma,
            lower_ms=70.0,
            upper_ms=150.0,
        )
        post_pause_count = max(1, int(np.round(post_pause_ms / 1000.0 * cfg.sample_rate_hz)))
        post_pause_start = len(points)
        points.extend([(xt, yt)] * post_pause_count)
        phase_ranges["post_click_pause"] = (post_pause_start, len(points))

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
        event_segments.append(EventSegment("pause", *phase_ranges["post_click_pause"]))

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
            "reaction_pause_ms": reaction_ms,
            "post_pause_ms": post_pause_ms,
            "peak_fraction": peak_fraction,
            "correction_count": correction_count,
            "overshoot_like_correction": bool(correction_count > 0),
            "tremor_enabled": bool(distance > 32.0),
        }
        return SyntheticAgentTrajectory(session=session, diagnostics=diagnostics)

    @staticmethod
    def _minimum_jerk(progress: float) -> float:
        value = float(np.clip(progress, 0.0, 1.0))
        return 10.0 * value**3 - 15.0 * value**4 + 6.0 * value**5

    @staticmethod
    def _quintic_segment(start: np.ndarray, end: np.ndarray, steps: int) -> list[tuple[float, float]]:
        if steps <= 0:
            return []
        start_point = np.asarray(start, dtype=np.float64)
        delta = np.asarray(end, dtype=np.float64) - start_point
        points: list[tuple[float, float]] = []
        for index in range(1, steps + 1):
            progress = SyntheticAgent._minimum_jerk(index / steps)
            point = start_point + delta * progress
            points.append((float(point[0]), float(point[1])))
        return points

    @staticmethod
    def _asymmetric_progress(progress: float, peak_fraction: float) -> float:
        if progress <= peak_fraction:
            return 0.5 * progress / max(peak_fraction, np.finfo(float).eps)
        return 0.5 + 0.5 * (progress - peak_fraction) / max(1.0 - peak_fraction, np.finfo(float).eps)

    @staticmethod
    def _sample_lognormal_ms(
        rng: np.random.Generator,
        *,
        mu: float,
        sigma: float,
        lower_ms: float,
        upper_ms: float,
    ) -> float:
        sample = float(rng.lognormal(mu, sigma))
        return float(np.clip(sample, lower_ms, upper_ms))

    @staticmethod
    def _make_tremor_profile(
        rng: np.random.Generator,
        *,
        count: int,
        scale_px: float,
        enabled: bool,
    ) -> np.ndarray:
        if count <= 0 or not enabled or scale_px <= 0.0:
            return np.zeros(max(count, 0), dtype=np.float64)
        u = np.linspace(0.0, 1.0, count, endpoint=True)
        carrier = np.zeros(count, dtype=np.float64)
        for frequency, amplitude in zip(rng.integers(7, 15, size=3), rng.normal(1.0, 0.25, size=3)):
            phase = float(rng.uniform(0.0, 2.0 * np.pi))
            carrier += amplitude * np.sin(2.0 * np.pi * float(frequency) * u + phase)
        carrier -= float(np.mean(carrier))
        carrier /= max(float(np.std(carrier)), np.finfo(float).eps)
        ramp_in_progress = np.clip((u - 0.42) / 0.22, 0.0, 1.0)
        ramp_out_progress = np.clip((u - 0.88) / 0.12, 0.0, 1.0)
        ramp_in = 10.0 * ramp_in_progress**3 - 15.0 * ramp_in_progress**4 + 6.0 * ramp_in_progress**5
        ramp_out = 1.0 - (10.0 * ramp_out_progress**3 - 15.0 * ramp_out_progress**4 + 6.0 * ramp_out_progress**5)
        window = ramp_in * ramp_out
        return carrier * window * scale_px


__all__ = ["SyntheticAgent", "SyntheticAgentConfig", "SyntheticAgentTrajectory"]
