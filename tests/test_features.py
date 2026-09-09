from __future__ import annotations

import numpy as np

from cv_agent.analytics import EventSegment, TrajectoryFeatureExtractor, TrajectorySession


def make_session() -> TrajectorySession:
    timestamps = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    x = [0.0, 0.0, 10.0, 25.0, 35.0, 32.0, 40.0]
    y = [0.0] * len(x)
    dx = [0, 0, 10, 15, 10, -3, 8]
    dy = [0] * len(x)
    return TrajectorySession(
        session_id="feature-test",
        source="human",
        target_distance_px=40.0,
        target_size_px=20.0,
        reaction_time_ms=0.0,
        timestamps=timestamps,
        x=x,
        y=y,
        dx=dx,
        dy=dy,
        event_segments=[EventSegment("micro_correction", 4, 6)],
    )


def test_extracts_kinematic_and_event_features() -> None:
    features = TrajectoryFeatureExtractor().extract(make_session())
    assert features["path_length"] > features["displacement"]
    assert 0.0 < features["straightness"] <= 1.0
    assert features["speed_mean"] > 0.0
    assert features["reaction_time_ms"] == 100.0
    assert features["correction_count"] == 1
    assert features["overshoot"] is True


def test_frequency_features_are_finite_and_guard_short_sequences() -> None:
    features = TrajectoryFeatureExtractor().extract(make_session())
    assert np.isfinite(features["hf_lf_energy_ratio"])
    assert 0.0 <= features["spectral_entropy"] <= 1.0
    short = TrajectorySession(
        session_id="short",
        source="bot",
        target_distance_px=0.0,
        target_size_px=0.0,
        reaction_time_ms=0.0,
        timestamps=[0.0, 0.1],
        x=[0.0, 0.0],
        y=[0.0, 0.0],
        dx=[0, 0],
        dy=[0, 0],
    )
    short_features = TrajectoryFeatureExtractor().extract(short)
    assert short_features["hf_lf_energy_ratio"] == 0.0
    assert short_features["spectral_entropy"] == 0.0
    assert all(np.isfinite(float(value)) for value in short_features.values() if isinstance(value, (int, float)))
