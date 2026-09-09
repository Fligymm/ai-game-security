"""Offline binary/multiclass baseline detectors for trajectory research."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import numpy as np
import joblib
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, classification_report, confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

CLASS_NAMES = {0: "human", 1: "bot_agent", 2: "synthetic"}


def _load_feature_file(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected an object in {path}")
    records = []
    for session_id, values in payload.items():
        if not isinstance(values, dict):
            continue
        row = {}
        for name, value in values.items():
            if isinstance(value, bool):
                row[name] = float(value)
            elif isinstance(value, (int, float)) and np.isfinite(value):
                row[name] = float(value)
            elif value is None:
                row[name] = np.nan
        if row:
            records.append((str(session_id), row))
    return records


def _load_dataset(data_root: str | Path, *, binary: bool = False):
    root = Path(data_root)
    grouped = []
    for directory in ("human", "bot_agent", "synthetic"):
        path = root / directory / "features.json"
        if path.exists():
            label = 0 if directory == "human" else (1 if binary else {"human": 0, "bot_agent": 1, "synthetic": 2}[directory])
            grouped.extend((sid, label, row) for sid, row in _load_feature_file(path))
    if not grouped:
        raise FileNotFoundError(f"no features.json found below {root}")
    names = sorted({name for _, _, row in grouped for name in row})
    X = np.full((len(grouped), len(names)), np.nan, dtype=float)
    y = np.empty(len(grouped), dtype=np.int64)
    ids = []
    for i, (sid, label, row) in enumerate(grouped):
        ids.append(sid)
        y[i] = label
        for j, name in enumerate(names):
            if name in row:
                X[i, j] = row[name]
    if len(np.unique(y)) < 2:
        raise ValueError("at least two classes are required")
    return X, y, names, ids


def _tpr_at_one_percent_fpr(y_true, scores) -> float:
    fpr, tpr, _ = roc_curve(y_true, scores)
    eligible = tpr[fpr <= 0.01]
    return float(np.max(eligible)) if len(eligible) else 0.0


def train_and_eval(data_root: str | Path = "datasets", *, binary: bool = False, random_state: int = 42,
                   n_splits: int = 5, report_path: str | Path | None = None,
                   model_path: str | Path = "models/baseline_detector.joblib",
                   print_fn: Callable[[str], None] = print) -> dict[str, object]:
    """Train detectors and return metrics, OOF predictions, and feature rankings."""
    root = Path(data_root)
    X, y, feature_names, session_ids = _load_dataset(root, binary=binary)
    labels = sorted(np.unique(y).tolist())
    display_names = ["human", "bot"] if binary else [CLASS_NAMES[label] for label in labels]
    isolation = Pipeline([("preprocess", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])),
                          ("model", IsolationForest(contamination=0.05, random_state=random_state))])
    isolation.fit(X[y == 0])
    isolation_scores = -isolation.decision_function(X)
    isolation_auc = float(roc_auc_score(y != 0, isolation_scores))
    if np.min(np.bincount(y)) < n_splits:
        raise ValueError(f"each class needs at least {n_splits} samples")
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    oof_scores = np.full((len(y), len(labels)), np.nan)
    oof_predictions = np.empty(len(y), dtype=np.int64)
    fold_importances = []
    for train_index, test_index in splitter.split(X, y):
        forest = Pipeline([("preprocess", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])),
                           ("model", RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=random_state, n_jobs=-1))])
        forest.fit(X[train_index], y[train_index])
        probabilities = forest.predict_proba(X[test_index])
        oof_scores[test_index] = probabilities
        oof_predictions[test_index] = forest.classes_[np.argmax(probabilities, axis=1)]
        fold_importances.append(forest.named_steps["model"].feature_importances_)
    cm = confusion_matrix(y, oof_predictions, labels=labels)
    report = classification_report(y, oof_predictions, labels=labels, target_names=display_names, output_dict=True, zero_division=0)
    if binary:
        rf_auc = float(roc_auc_score(y, oof_scores[:, 1]))
        rf_pr_auc = float(average_precision_score(y, oof_scores[:, 1]))
        tpr = _tpr_at_one_percent_fpr(y, oof_scores[:, 1])
    else:
        rf_auc = float(roc_auc_score(y, oof_scores, multi_class="ovr", average="macro", labels=labels))
        rf_pr_auc = float(average_precision_score(y, oof_scores, average="macro"))
        tpr = None
    mean_importance = np.mean(np.vstack(fold_importances), axis=0)
    ranked = sorted(((feature_names[i], float(mean_importance[i])) for i in range(len(feature_names))), key=lambda item: item[1], reverse=True)
    total = max(sum(value for _, value in ranked), np.finfo(float).eps)
    cumulative = 0.0
    feature_importance = []
    for name, value in ranked[:10]:
        cumulative += value / total
        feature_importance.append({"feature": name, "importance": value, "relative_weight": value / total, "cumulative_weight": cumulative})

    final_imputer = SimpleImputer(strategy="median")
    final_scaler = StandardScaler()
    X_imputed = final_imputer.fit_transform(X)
    X_scaled = final_scaler.fit_transform(X_imputed)
    final_forest = RandomForestClassifier(
        n_estimators=300, class_weight="balanced", random_state=random_state, n_jobs=-1,
    )
    final_forest.fit(X_scaled, y)
    model_file = Path(model_path)
    model_file.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": final_forest,
        "imputer": final_imputer,
        "scaler": final_scaler,
        "feature_names": feature_names,
        "class_mapping": {str(k): v for k, v in (({0: "human", 1: "bot"}).items() if binary else CLASS_NAMES.items())},
        "mode": "binary" if binary else "multiclass",
    }, model_file)
    print_fn(f"[INFO] Loaded {len(y)} sessions, {len(feature_names)} features ({'binary' if binary else '3-class'})")
    print_fn(f"[Isolation Forest] ROC-AUC: {isolation_auc:.4f}")
    print_fn(f"[Random Forest] ROC-AUC: {rf_auc:.4f}")
    print_fn(f"[Random Forest] PR-AUC: {rf_pr_auc:.4f}")
    if tpr is not None:
        print_fn(f"[Random Forest] TPR at FPR <= 1%: {tpr:.4f}")
    print_fn("[Random Forest] Confusion matrix:")
    print_fn(str(cm.tolist()))
    print_fn("[Random Forest] Classification report:")
    print_fn(classification_report(y, oof_predictions, labels=labels, target_names=display_names, zero_division=0))
    print_fn("[Random Forest] Top features:")
    for item in feature_importance:
        print_fn(f"  {item['feature']}: {item['relative_weight']:.2%} (cumulative {item['cumulative_weight']:.2%})")
    result = {"mode": "binary" if binary else "multiclass", "class_mapping": {str(k): v for k, v in (({0: "human", 1: "bot"}).items() if binary else CLASS_NAMES.items())},
              "feature_names": feature_names, "session_ids": session_ids, "X": X, "y": y, "isolation_forest": isolation,
              "isolation_scores": isolation_scores, "isolation_roc_auc": isolation_auc, "random_forest_oof_scores": oof_scores,
              "random_forest_oof_predictions": oof_predictions, "random_forest_roc_auc": rf_auc, "random_forest_pr_auc": rf_pr_auc,
              "random_forest_tpr_at_fpr_1pct": tpr, "confusion_matrix": cm, "classification_report": report,
              "feature_importance": feature_importance, "top_features": [(item["feature"], item["importance"]) for item in feature_importance]}
    serializable = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in result.items() if k not in {"X", "isolation_forest"}}
    report_file = Path(report_path) if report_path is not None else root / "evaluation_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(serializable, indent=2, default=str), encoding="utf-8")
    print_fn(f"[INFO] Evaluation report: {report_file}")
    print_fn(f"[INFO] Baseline detector model saved to {model_file}")
    result["report_path"] = report_file
    result["model_path"] = model_file
    result["model"] = final_forest
    result["imputer"] = final_imputer
    result["scaler"] = final_scaler
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train offline trajectory anti-cheat baselines")
    parser.add_argument("--data-root", type=Path, default=Path("datasets"))
    parser.add_argument("--splits", type=int, default=5)
    parser.add_argument("--binary", action="store_true", help="use legacy human-vs-bot labels")
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--model-path", type=Path, default=Path("models/baseline_detector.joblib"))
    args = parser.parse_args()
    train_and_eval(args.data_root, binary=args.binary, n_splits=args.splits, report_path=args.report_path, model_path=args.model_path)


if __name__ == "__main__":
    main()
