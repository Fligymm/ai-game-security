"""Offline baseline detectors for trajectory anti-cheat research."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BOT_DIRS = ("bot_agent", "synthetic")
NON_BOT_DIRS = ("human",)


def _load_feature_file(path: Path) -> list[tuple[str, dict[str, float]]]:
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


def _load_dataset(data_root: str | Path):
    root = Path(data_root)
    grouped = []
    for directory in (*BOT_DIRS, *NON_BOT_DIRS):
        path = root / directory / "features.json"
        if path.exists():
            label = 1 if directory in BOT_DIRS else 0
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
        raise ValueError("both Bot and Non-Bot classes are required")
    return X, y, names, ids


def _tpr_at_one_percent_fpr(y_true, scores) -> float:
    fpr, tpr, _ = roc_curve(y_true, scores)
    values = tpr[fpr <= 0.01]
    return float(np.max(values)) if len(values) else 0.0


def train_and_eval(
    data_root: str | Path = "datasets",
    *,
    random_state: int = 42,
    n_splits: int = 5,
    print_fn: Callable[[str], None] = print,
) -> dict[str, object]:
    """Train baselines and return out-of-fold metrics plus fitted artifacts."""
    X, y, feature_names, session_ids = _load_dataset(data_root)
    prep = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    isolation = Pipeline([
        ("preprocess", prep),
        ("model", IsolationForest(contamination=0.05, random_state=random_state)),
    ])
    isolation.fit(X[y == 0])
    isolation_scores = -isolation.decision_function(X)
    isolation_auc = float(roc_auc_score(y, isolation_scores))

    if np.min(np.bincount(y)) < n_splits:
        raise ValueError(f"each class needs at least {n_splits} samples")
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    oof_scores = np.full(len(y), np.nan)
    fold_importances = []
    for train_index, test_index in splitter.split(X, y):
        forest = Pipeline([
            ("preprocess", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ])),
            ("model", RandomForestClassifier(
                n_estimators=300,
                class_weight="balanced",
                random_state=random_state,
                n_jobs=-1,
            )),
        ])
        forest.fit(X[train_index], y[train_index])
        oof_scores[test_index] = forest.predict_proba(X[test_index])[:, 1]
        fold_importances.append(forest.named_steps["model"].feature_importances_)

    rf_auc = float(roc_auc_score(y, oof_scores))
    rf_pr_auc = float(average_precision_score(y, oof_scores))
    mean_importance = np.mean(np.vstack(fold_importances), axis=0)
    top_features = sorted(
        ((feature_names[i], float(mean_importance[i])) for i in range(len(feature_names))),
        key=lambda item: item[1], reverse=True,
    )[:8]
    tpr = _tpr_at_one_percent_fpr(y, oof_scores)
    print_fn(f"[INFO] Loaded {len(y)} sessions, {len(feature_names)} features")
    print_fn(f"[INFO] Class counts: non_bot={int(np.sum(y == 0))}, bot={int(np.sum(y == 1))}")
    print_fn(f"[Isolation Forest] ROC-AUC: {isolation_auc:.4f}")
    print_fn(f"[Random Forest] ROC-AUC: {rf_auc:.4f}")
    print_fn(f"[Random Forest] PR-AUC: {rf_pr_auc:.4f}")
    print_fn(f"[Random Forest] TPR at FPR <= 1%: {tpr:.4f}")
    print_fn("[Random Forest] Top features:")
    for name, importance in top_features:
        print_fn(f"  {name}: {importance:.6f}")
    return {
        "feature_names": feature_names,
        "session_ids": session_ids,
        "X": X,
        "y": y,
        "isolation_forest": isolation,
        "isolation_scores": isolation_scores,
        "isolation_roc_auc": isolation_auc,
        "random_forest_oof_scores": oof_scores,
        "random_forest_roc_auc": rf_auc,
        "random_forest_pr_auc": rf_pr_auc,
        "random_forest_tpr_at_fpr_1pct": tpr,
        "top_features": top_features,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train offline trajectory anti-cheat baselines")
    parser.add_argument("--data-root", type=Path, default=Path("datasets"))
    parser.add_argument("--splits", type=int, default=5)
    args = parser.parse_args()
    train_and_eval(args.data_root, n_splits=args.splits)


if __name__ == "__main__":
    main()
