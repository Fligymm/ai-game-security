"""Multi-dimensional trajectory features for offline behavior analysis."""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np

from .trajectory_schema import TrajectorySession


class TrajectoryFeatureExtractor:
    """Extract kinematic, event, and frequency-domain features."""

    def __init__(self, *, movement_threshold_px: float = 1.0, zero_speed_threshold_px_s: float = 1.0) -> None:
        if movement_threshold_px < 0 or zero_speed_threshold_px_s < 0:
            raise ValueError("feature thresholds must be non-negative")
        self.movement_threshold_px = float(movement_threshold_px)
        self.zero_speed_threshold_px_s = float(zero_speed_threshold_px_s)

    def extract(self, session: TrajectorySession) -> dict[str, float | bool | int]:
        timestamps = np.asarray(session.timestamps, dtype=np.float64)
        positions = np.column_stack((session.x, session.y)).astype(np.float64, copy=False)
        dt = np.diff(timestamps)
        segments = np.diff(positions, axis=0)
        speeds = np.linalg.norm(segments, axis=1) / np.maximum(dt, np.finfo(float).eps) if len(dt) else np.empty(0)

        displacement = float(np.linalg.norm(positions[-1] - positions[0])) if len(positions) else 0.0
        path_length = float(np.sum(np.linalg.norm(segments, axis=1))) if len(segments) else 0.0
        acceleration = self._derivative(np.column_stack((np.zeros(0), np.zeros(0))), timestamps)
        if len(positions) >= 3:
            velocity = self._derivative(positions, timestamps)
            acceleration = self._derivative(velocity, timestamps)
        jerk = self._derivative(acceleration, timestamps) if len(acceleration) >= 4 else np.empty((0, 2))
        jerk_mag = np.linalg.norm(jerk, axis=1) if len(jerk) else np.empty(0)

        result: dict[str, float | bool | int] = {
            "path_length": path_length,
            "displacement": displacement,
            "straightness": displacement / max(path_length, np.finfo(float).eps),
            "speed_mean": float(np.mean(speeds)) if len(speeds) else 0.0,
            "speed_std": float(np.std(speeds)) if len(speeds) else 0.0,
            "speed_cv": self._coefficient_of_variation(speeds),
            "acceleration_rms": self._rms(np.linalg.norm(acceleration, axis=1)) if len(acceleration) else 0.0,
            "jerk_mean": float(np.mean(jerk_mag)) if len(jerk_mag) else 0.0,
            "jerk_rms": self._rms(jerk_mag),
            "reaction_time_ms": self._reaction_time_ms(session, segments),
            "correction_count": self._correction_count(session, segments),
            "overshoot": self._overshoot(session, segments),
            "zero_speed_fraction": self._zero_speed_fraction(speeds, dt),
        }
        result.update(self._frequency_features(speeds, timestamps))
        return result

    def _reaction_time_ms(self, session: TrajectorySession, segments: np.ndarray) -> float:
        if not len(session.timestamps) or not len(segments):
            return 0.0
        magnitudes = np.linalg.norm(segments, axis=1)
        indices = np.flatnonzero(magnitudes >= self.movement_threshold_px)
        return float(session.timestamps[int(indices[0])] * 1000.0) if len(indices) else 0.0

    def _correction_count(self, session: TrajectorySession, segments: np.ndarray) -> int:
        labeled = sum(1 for event in session.event_segments if event.phase == "micro_correction")
        if labeled:
            return int(labeled)
        if len(segments) < 2:
            return 0
        movement = segments[np.linalg.norm(segments, axis=1) >= self.movement_threshold_px]
        if len(movement) < 2:
            return 0
        return int(sum(float(np.dot(previous, current)) < 0.0 for previous, current in zip(movement, movement[1:])))

    def _overshoot(self, session: TrajectorySession, segments: np.ndarray) -> bool:
        if any(event.phase == "micro_correction" for event in session.event_segments):
            return any(
                float(np.dot(segments[index - 1], segments[index])) < 0.0
                for index in range(1, len(segments))
            )
        return self._correction_count(session, segments) > 0

    def _frequency_features(self, speeds: np.ndarray, timestamps: np.ndarray) -> dict[str, float]:
        if len(speeds) < 4:
            return {"hf_lf_energy_ratio": 0.0, "spectral_entropy": 0.0}
        sample_times = timestamps[:-1]
        duration = float(sample_times[-1] - sample_times[0]) if len(sample_times) > 1 else 0.0
        if duration <= 0.0:
            return {"hf_lf_energy_ratio": 0.0, "spectral_entropy": 0.0}
        uniform_times = np.linspace(sample_times[0], sample_times[-1], len(speeds))
        uniform_speed = np.interp(uniform_times, sample_times, speeds)
        centered = uniform_speed - np.mean(uniform_speed)
        power = np.abs(np.fft.rfft(centered)) ** 2
        if len(power) <= 1:
            return {"hf_lf_energy_ratio": 0.0, "spectral_entropy": 0.0}
        power = power[1:]
        frequencies = np.fft.rfftfreq(len(centered), d=duration / max(len(centered) - 1, 1))[1:]
        midpoint = float(np.median(frequencies)) if len(frequencies) else 0.0
        low_energy = float(np.sum(power[frequencies <= midpoint]))
        high_energy = float(np.sum(power[frequencies > midpoint]))
        probabilities = power / max(float(np.sum(power)), np.finfo(float).eps)
        entropy = float(-np.sum(probabilities * np.log2(np.maximum(probabilities, np.finfo(float).eps))))
        entropy /= max(math.log2(len(probabilities)), 1.0)
        return {
            "hf_lf_energy_ratio": high_energy / max(low_energy, np.finfo(float).eps),
            "spectral_entropy": entropy,
        }

    @staticmethod
    def _derivative(values: np.ndarray, timestamps: np.ndarray) -> np.ndarray:
        if len(values) < 3:
            return np.zeros_like(values)
        return np.column_stack(
            [np.gradient(values[:, axis], timestamps, edge_order=1) for axis in range(values.shape[1])]
        )

    @staticmethod
    def _rms(values: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(values)))) if len(values) else 0.0

    @staticmethod
    def _coefficient_of_variation(values: np.ndarray) -> float:
        if not len(values):
            return 0.0
        mean = float(np.mean(values))
        return float(np.std(values) / mean) if mean > np.finfo(float).eps else 0.0

    def _zero_speed_fraction(self, speeds: np.ndarray, dt: np.ndarray) -> float:
        if not len(dt) or not len(speeds):
            return 1.0
        weights = dt[: len(speeds)]
        return float(np.sum(weights[speeds <= self.zero_speed_threshold_px_s]) / max(np.sum(weights), np.finfo(float).eps))


__all__ = ["TrajectoryFeatureExtractor"]
