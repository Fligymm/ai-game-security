from __future__ import annotations

import json

import numpy as np

from cv_agent.analytics import TrajectoryFeatureExtractor, TrajectorySession
from cv_agent.simulation.synthetic_agent import SyntheticAgent


def _make_sharp_baseline_session() -> TrajectorySession:
    start = np.array([10.0, 20.0], dtype=np.float64)
    target = np.array([210.0, 140.0], dtype=np.float64)
    vector = target - start
    direction = vector / np.linalg.norm(vector)
    perpendicular = np.array([-direction[1], direction[0]], dtype=np.float64)
    midpoint = start + vector * 0.34 + perpendicular * 90.0

    sample_rate_hz = 120.0
    reaction_frames = 18
    move_frames = 14
    settle_frames = 14
    dt = 1.0 / sample_rate_hz

    points: list[tuple[float, float]] = [(float(start[0]), float(start[1]))] * reaction_frames
    for index in range(1, move_frames + 1):
        u = index / move_frames
        point = start + (midpoint - start) * u
        points.append((float(point[0]), float(point[1])))
    for index in range(1, move_frames + 1):
        u = index / move_frames
        point = midpoint + (target - midpoint) * u
        points.append((float(point[0]), float(point[1])))
    points.extend([(float(target[0]), float(target[1]))] * settle_frames)

    timestamps = [index * dt for index in range(len(points))]
    positions = np.asarray(points, dtype=np.float64)
    deltas = np.diff(positions, axis=0)
    dx = [0] + [int(round(value)) for value in deltas[:, 0]]
    dy = [0] + [int(round(value)) for value in deltas[:, 1]]
    return TrajectorySession(
        session_id="baseline",
        source="human",
        target_distance_px=float(np.linalg.norm(vector)),
        target_size_px=20.0,
        reaction_time_ms=reaction_frames * dt * 1000.0,
        timestamps=timestamps,
        x=[float(value) for value in positions[:, 0]],
        y=[float(value) for value in positions[:, 1]],
        dx=dx,
        dy=dy,
    )


def test_quintic_generation_reduces_jerk_against_sharp_baseline() -> None:
    extractor = TrajectoryFeatureExtractor()
    optimized = SyntheticAgent().generate((10.0, 20.0), (210.0, 140.0), session_id="synthetic-stealth", seed=7)
    baseline = _make_sharp_baseline_session()

    optimized_features = extractor.extract(optimized.session)
    baseline_features = extractor.extract(baseline)

    assert optimized_features["jerk_rms"] < baseline_features["jerk_rms"]
    assert optimized_features["jerk_mean"] < baseline_features["jerk_mean"]


def test_zero_speed_fraction_stays_in_human_like_band() -> None:
    extractor = TrajectoryFeatureExtractor()
    fractions = []
    for seed in range(5):
        session = SyntheticAgent().generate((10.0, 20.0), (210.0, 140.0), session_id=f"synthetic-{seed}", seed=seed).session
        features = extractor.extract(session)
        fractions.append(features["zero_speed_fraction"])
        assert 0.08 < features["zero_speed_fraction"] < 0.35

    assert float(np.mean(fractions)) > 0.12


def test_export_and_feature_extraction_round_trip(tmp_path) -> None:
    result = SyntheticAgent().generate((10.0, 20.0), (210.0, 140.0), session_id="synthetic-roundtrip", seed=11)
    path = result.save_json(tmp_path / "synthetic.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    restored = TrajectorySession.from_dict(payload)
    features = TrajectoryFeatureExtractor().extract(restored)

    assert payload["metadata"]["source"] == "synthetic_adversarial"
    assert restored.frame_count == len(restored.timestamps)
    assert restored.x[-1] == 210.0
    assert restored.y[-1] == 140.0
    assert np.isfinite(features["jerk_rms"])
    assert np.isfinite(features["zero_speed_fraction"])
