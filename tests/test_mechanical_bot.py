from __future__ import annotations

import pytest

from cv_agent.analytics import TrajectoryFeatureExtractor
from cv_agent.simulation import MechanicalBotAgent


def test_mechanical_bot_is_linear_and_immediate() -> None:
    trajectory = MechanicalBotAgent().generate((0.0, 0.0), (300.0, 400.0), session_id="mechanical")
    session = trajectory.session
    features = TrajectoryFeatureExtractor().extract(session)

    assert session.source == "bot_agent"
    assert session.reaction_time_ms == 0.0
    assert features["straightness"] == pytest.approx(1.0)
    assert features["zero_speed_fraction"] == pytest.approx(0.0)
    assert features["correction_count"] == 0
    assert not features["overshoot"]
    assert [event.phase for event in session.event_segments] == ["coarse_move"]


def test_mechanical_bot_has_constant_speed_extreme() -> None:
    session = MechanicalBotAgent(speed_px_s=1500.0).generate(
        (10.0, 20.0), (610.0, 20.0), session_id="constant-speed"
    ).session
    features = TrajectoryFeatureExtractor().extract(session)
    assert features["speed_cv"] == pytest.approx(0.0, abs=1e-12)
    assert features["jerk_rms"] == pytest.approx(0.0, abs=1e-6)
