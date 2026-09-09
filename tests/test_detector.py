from __future__ import annotations

import json

from tools.train_baseline_detector import train_and_eval


def test_train_and_eval_on_tiny_feature_dataset(tmp_path) -> None:
    for directory, prefix in (("human", "human"), ("bot_agent", "bot"), ("synthetic", "synthetic")):
        target = tmp_path / directory
        target.mkdir(parents=True)
        payload = {
            f"{prefix}_{index}": {
                "straightness": 0.2 + index * 0.01 if prefix == "human" else (0.9 if prefix == "bot" else 0.7),
                "jerk_rms": None if index == 0 else (10.0 if prefix == "human" else (100.0 if prefix == "bot" else 60.0)) + index,
                "spectral_entropy": 0.4 if prefix == "human" else (0.8 if prefix == "bot" else 0.6),
            }
            for index in range(5)
        }
        (target / "features.json").write_text(json.dumps(payload), encoding="utf-8")
    result = train_and_eval(tmp_path, n_splits=5, print_fn=lambda _: None)
    assert result["X"].shape == (15, 3)
    assert result["mode"] == "multiclass"
    assert result["confusion_matrix"].shape == (3, 3)
    assert set(result["class_mapping"].values()) == {"human", "bot_agent", "synthetic"}
    assert 0.0 <= result["random_forest_roc_auc"] <= 1.0
    assert 0.0 <= result["random_forest_pr_auc"] <= 1.0
    assert len(result["top_features"]) == 3
    assert (tmp_path / "evaluation_report.json").exists()


def test_binary_compatibility(tmp_path) -> None:
    for directory in ("human", "bot_agent"):
        target = tmp_path / directory
        target.mkdir(parents=True)
        payload = {str(i): {"jerk_rms": float(i + (100 if directory == "bot_agent" else 0))} for i in range(5)}
        (target / "features.json").write_text(json.dumps(payload), encoding="utf-8")
    result = train_and_eval(tmp_path, binary=True, n_splits=5, print_fn=lambda _: None)
    assert result["mode"] == "binary"
    assert result["confusion_matrix"].shape == (2, 2)
