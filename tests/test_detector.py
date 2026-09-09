from __future__ import annotations

import json

from tools.train_baseline_detector import train_and_eval


def test_train_and_eval_on_tiny_feature_dataset(tmp_path) -> None:
    for directory, prefix in (("human", "human"), ("bot_agent", "bot")):
        target = tmp_path / directory
        target.mkdir(parents=True)
        payload = {
            f"{prefix}_{index}": {
                "straightness": 0.2 + index * 0.01 if prefix == "human" else 0.9,
                "jerk_rms": None if index == 0 else (10.0 + index if prefix == "human" else 100.0 + index),
                "spectral_entropy": 0.4 if prefix == "human" else 0.8,
            }
            for index in range(5)
        }
        (target / "features.json").write_text(json.dumps(payload), encoding="utf-8")
    result = train_and_eval(tmp_path, n_splits=5, print_fn=lambda _: None)
    assert result["X"].shape == (10, 3)
    assert 0.0 <= result["random_forest_roc_auc"] <= 1.0
    assert 0.0 <= result["random_forest_pr_auc"] <= 1.0
    assert len(result["top_features"]) == 3
