from __future__ import annotations

import json

import numpy as np

from cv_agent.analytics import (
    TrajectoryFeatureExtractor,
    TrajectorySession,
)
from cv_agent.simulation.synthetic_agent import SyntheticAgent


def make_session(*, timestamps=None, x=None, y=None, dx=None, dy=None) -> TrajectorySession:
    return TrajectorySession(
        session_id="analytics-test",
        source="bot",
        target_distance_px=100.0,
        target_size_px=20.0,
        reaction_time_ms=100.0,
        timestamps=[] if timestamps is None else timestamps,
        x=[] if x is None else x,
        y=[] if y is None else y,
        dx=[] if dx is None else dx,
        dy=[] if dy is None else dy,
    )


def test_nested_schema_round_trip() -> None:
    session = make_session(
        timestamps=[0.0, 0.1, 0.2],
        x=[0.0, 3.0, 6.0],
        y=[0.0, 4.0, 8.0],
        dx=[0, 3, 3],
        dy=[0, 4, 4],
    )
    encoded = session.to_dict()
    restored = TrajectorySession.from_dict(json.loads(json.dumps(encoded)))
    assert encoded["metadata"]["source"] == "bot"
    assert encoded["time_series"]["dx"] == [0, 3, 3]
    assert restored.to_dict() == encoded


def test_zero_and_short_sequences_are_finite() -> None:
    extractor = TrajectoryFeatureExtractor()
    for session in (
        make_session(),
        make_session(timestamps=[0.0], x=[0.0], y=[0.0], dx=[0], dy=[0]),
        make_session(
            timestamps=[0.0, 0.1, 0.2],
            x=[0.0, 0.0, 0.0],
            y=[0.0, 0.0, 0.0],
            dx=[0, 0, 0],
            dy=[0, 0, 0],
        ),
    ):
        features = extractor.extract(session)
        numeric = [value for value in features.values() if isinstance(value, (int, float))]
        assert all(np.isfinite(numeric))
        assert features["path_length"] == 0.0
        assert features["displacement"] == 0.0
        assert features["straightness"] == 0.0


def test_synthetic_agent_exports_canonical_json(tmp_path) -> None:
    result = SyntheticAgent().generate((10.0, 20.0), (210.0, 140.0), session_id="synthetic-test", seed=42)
    path = result.save_json(tmp_path / "synthetic.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    restored = TrajectorySession.from_dict(payload)
    assert payload["metadata"]["source"] == "synthetic_adversarial"
    assert restored.frame_count == len(restored.timestamps)
    assert restored.x[-1] == 210.0
    assert restored.y[-1] == 140.0
    assert restored.seed == 42
