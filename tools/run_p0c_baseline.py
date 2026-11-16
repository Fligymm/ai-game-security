"""Session-level P0-C pilot baseline (3 H vs 3 B).

This is intentionally small: it uses leave-one-session-out (LOO) and reports
pilot metrics only. It must not be presented as a general anti-cheat classifier.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


FEATURE_NAMES = [
    "detection_frame_ratio",
    "selected_frame_ratio",
    "mean_detections_per_frame",
    "selected_head_ratio",
    "unique_selected_tracks",
    "track_switches_per_frame",
    "acquisition_episodes_per_frame",
    "selected_episode_duration_mean_s",
    "selected_episode_duration_max_s",
    "mean_offset_px",
    "median_offset_px",
    "p95_offset_px",
    "mean_selected_confidence",
]


def _ratio(value: float | None, denominator: int) -> float:
    return float(value) if value is not None else 0.0 if denominator else 0.0


def feature_row(summary: dict[str, Any]) -> dict[str, float]:
    frames = max(int(summary.get("frames") or 1), 1)
    class_counts = summary.get("selected_class_counts") or {}
    head = float(class_counts.get("enemy_head", 0))
    body = float(class_counts.get("enemy_body", 0))
    selected = head + body
    return {
        "detection_frame_ratio": float(summary.get("detection_frame_ratio") or 0.0),
        "selected_frame_ratio": float(summary.get("selected_frame_ratio") or 0.0),
        "mean_detections_per_frame": float(summary.get("mean_detections_per_frame") or 0.0),
        "selected_head_ratio": (head / selected) if selected else 0.0,
        "unique_selected_tracks": float(summary.get("unique_selected_tracks") or 0),
        "track_switches_per_frame": float(summary.get("track_switches") or 0) / frames,
        "acquisition_episodes_per_frame": float(summary.get("acquisition_episodes") or 0) / frames,
        "selected_episode_duration_mean_s": float(summary.get("selected_episode_duration_mean_s") or 0.0),
        "selected_episode_duration_max_s": float(summary.get("selected_episode_duration_max_s") or 0.0),
        "mean_offset_px": _ratio(summary.get("mean_offset_px"), frames),
        "median_offset_px": _ratio(summary.get("median_offset_px"), frames),
        "p95_offset_px": _ratio(summary.get("p95_offset_px"), frames),
        "mean_selected_confidence": _ratio(summary.get("mean_selected_confidence"), frames),
    }


def _safe_auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    if len(set(y_true.tolist())) < 2:
        return None
    return float(roc_auc_score(y_true, scores))


def _load_feature_csv(path: Path) -> tuple[list[dict[str, float]], list[int], list[str], list[str], list[str]]:
    rows: list[dict[str, float]] = []
    y: list[int] = []
    ids: list[str] = []
    agents: list[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"empty features csv: {path}")
        feature_names = [
            name for name in reader.fieldnames
            if name not in {"session_id", "agent_type", "label"}
        ]
        for row in reader:
            agent = row.get("agent_type")
            if agent not in {"human", "game_bot"}:
                continue
            rows.append({name: float(row.get(name) or 0.0) for name in feature_names})
            y.append(0 if agent == "human" else 1)
            ids.append(str(row.get("session_id")))
            agents.append(str(agent))
    return rows, y, ids, agents, feature_names


def run_loo(
    summary_path: str | Path | None,
    output_dir: str | Path,
    *,
    features_csv: str | Path | None = None,
) -> dict[str, Any]:
    if features_csv is not None:
        rows, y, ids, agents, feature_names = _load_feature_csv(Path(features_csv))
        if len(rows) < 4:
            raise ValueError("need at least four sessions for a pilot baseline")
    else:
        if summary_path is None:
            raise ValueError("either summary_path or features_csv is required")
        payload = json.loads(Path(summary_path).read_text(encoding="utf-8"))
        summaries = payload.get("summaries", [])
        if len(summaries) < 4:
            raise ValueError("need at least four sessions for a pilot baseline")
        rows = []
        y = []
        ids = []
        agents = []
        feature_names = list(FEATURE_NAMES)
        for summary in summaries:
            agent = summary.get("agent_type")
            if agent not in {"human", "game_bot"}:
                continue
            rows.append(feature_row(summary))
            y.append(0 if agent == "human" else 1)
            ids.append(str(summary.get("source_session_id")))
            agents.append(str(agent))
    if len(set(y)) < 2:
        raise ValueError("need both human and game_bot sessions")

    X = np.asarray([[row[name] for name in feature_names] for row in rows], dtype=float)
    y_arr = np.asarray(y, dtype=int)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    models = {
        "dummy": DummyClassifier(strategy="most_frequent"),
        "logistic": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0)),
            ]
        ),
        "random_forest": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("model", RandomForestClassifier(
                    n_estimators=200,
                    max_depth=2,
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                )),
            ]
        ),
    }
    # A fixed majority baseline. Fitting DummyClassifier inside LOO is misleading
    # with a balanced 3/3 set: each training fold has only 2 samples of the held
    # out class, so the "majority" flips and the dummy systematically predicts
    # the wrong class.
    majority_label = int(np.argmax(np.bincount(y_arr)))
    predictions: dict[str, list[int]] = {name: [] for name in models}
    probabilities: dict[str, list[float]] = {name: [] for name in models}
    predictions["dummy"] = [majority_label] * len(y_arr)
    probabilities["dummy"] = [float(np.mean(y_arr))] * len(y_arr)
    loo = LeaveOneOut()
    for train_index, test_index in loo.split(X):
        for name in ("logistic", "random_forest"):
            model = models[name]
            model.fit(X[train_index], y_arr[train_index])
            pred = int(model.predict(X[test_index])[0])
            predictions[name].append(pred)
            if hasattr(model, "predict_proba"):
                p = model.predict_proba(X[test_index])[0]
                classes = list(getattr(model, "classes_", []))
                probabilities[name].append(float(p[classes.index(1)]) if 1 in classes else 0.5)
            else:
                probabilities[name].append(0.5)

    n_human = int(np.sum(y_arr == 0))
    n_bot = int(np.sum(y_arr == 1))
    results: dict[str, Any] = {
        "schema_version": "anticheat.p0c_baseline.v1",
        "description": f"leave-one-session-out pilot baseline; {n_human} H vs {n_bot} B",
        "n_sessions": len(y_arr),
        "class_counts": {"human": int(np.sum(y_arr == 0)), "game_bot": int(np.sum(y_arr == 1))},
        "features": feature_names,
        "sessions": [
            {"session_id": sid, "agent_type": agent, "label": int(label), **row}
            for sid, agent, label, row in zip(ids, agents, y_arr.tolist(), rows)
        ],
        "models": {},
    }
    for name in models:
        pred = np.asarray(predictions[name], dtype=int)
        proba = np.asarray(probabilities[name], dtype=float)
        results["models"][name] = {
            "accuracy": float(accuracy_score(y_arr, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y_arr, pred)),
            "roc_auc": _safe_auc(y_arr, proba),
            "confusion_matrix": confusion_matrix(y_arr, pred, labels=[0, 1]).tolist(),
            "classification_report": classification_report(
                y_arr, pred, labels=[0, 1], target_names=["human", "game_bot"], output_dict=True, zero_division=0
            ),
        }

    (output / "features.csv").write_text(
        "session_id,agent_type,label," + ",".join(feature_names) + "\n"
        + "\n".join(
            f"{sid},{agent},{label}," + ",".join(str(row[name]) for name in feature_names)
            for sid, agent, label, row in zip(ids, agents, y_arr.tolist(), rows)
        )
        + "\n",
        encoding="utf-8",
    )
    with (output / "loo_predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write("session_id,agent_type,y_true,dummy_pred,logistic_pred,logistic_proba,rf_pred,rf_proba\n")
        for i, (sid, agent, label) in enumerate(zip(ids, agents, y_arr.tolist())):
            handle.write(
                f"{sid},{agent},{label},{predictions['dummy'][i]},{predictions['logistic'][i]},"
                f"{probabilities['logistic'][i]:.6f},{predictions['random_forest'][i]},"
                f"{probabilities['random_forest'][i]:.6f}\n"
            )
    (output / "baseline_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run 3H/3B P0-C session-level LOO pilot baseline")
    parser.add_argument("--summary", type=Path, default=Path("runs/eval/anticheat_p0c/pilot_old_tiled_v2/summary.json"))
    parser.add_argument("--features-csv", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("runs/eval/anticheat_p0c/baseline_v1"))
    args = parser.parse_args(argv)
    try:
        results = run_loo(args.summary, args.output_dir, features_csv=args.features_csv)
    except Exception as exc:
        print(f"[ERROR] baseline failed: {exc}", file=sys.stderr)
        return 2
    print(f"[INFO] baseline output: {args.output_dir}")
    for name, metrics in results["models"].items():
        print(f"{name}: accuracy={metrics['accuracy']:.3f} balanced={metrics['balanced_accuracy']:.3f} auc={metrics['roc_auc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())