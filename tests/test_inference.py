from __future__ import annotations

import json

from cv_agent.analytics import TrajectoryDetector, TrajectorySession
from tools.train_baseline_detector import train_and_eval


def test_exported_model_predicts_trajectory_session(tmp_path) -> None:
    for directory, base in (("human", 0.1), ("bot_agent", 0.5), ("synthetic", 0.9)):
        target = tmp_path / directory
        target.mkdir(parents=True)
        payload = {
            f"{directory}_{index}": {
                "straightness": base + index * 0.001,
                "jerk_rms": base * 100.0 + index,
                "spectral_entropy": base,
            }
            for index in range(5)
        }
        (target / "features.json").write_text(json.dumps(payload), encoding="utf-8")

    model_path = tmp_path / "models" / "baseline_detector.joblib"
    train_and_eval(tmp_path, n_splits=5, model_path=model_path, print_fn=lambda _: None)
    session = TrajectorySession(
        session_id="inference-session",
        source="human",
        target_distance_px=100.0,
        target_size_px=20.0,
        reaction_time_ms=100.0,
        timestamps=[0.0, 0.1, 0.2, 0.3],
        x=[0.0, 10.0, 20.0, 30.0],
        y=[0.0, 0.0, 0.0, 0.0],
        dx=[0, 10, 10, 10],
        dy=[0, 0, 0, 0],
    )
    result = TrajectoryDetector(model_path).predict_session(session)
    assert result["prediction"] in {"human", "bot_agent", "synthetic"}
    assert set(result["probabilities"]) == {"human", "bot_agent", "synthetic"}
    assert abs(sum(result["probabilities"].values()) - 1.0) < 1e-9
