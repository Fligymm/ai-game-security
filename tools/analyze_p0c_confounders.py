"""Confounder analysis for P0-C fixed F2 tracking features.

Checks whether F2 differences are explained by target visibility/size/confidence
rather than behavior. Descriptive pilot analysis; no classifier is trained for
deployment.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


F2 = [
    "offset_mean_norm",
    "offset_median_norm",
    "offset_cv",
    "offset_slope",
    "settling_time_mean_s",
    "jitter_ratio",
]
CONFOUNDERS = [
    "target_area_median_norm",
    "visible_fraction",
    "target_confidence_mean",
    "visible_duration_median_s",
    "selected_fraction_of_visible",
]


def _load(path: Path) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    y = np.asarray([0 if row["agent_type"] == "human" else 1 for row in rows], dtype=int)
    ids = [row["session_id"] for row in rows]
    agents = [row["agent_type"] for row in rows]
    X = {name: np.asarray([float(row.get(name) or 0.0) for row in rows], dtype=float) for name in F2 + CONFOUNDERS}
    return y, X, ids, agents


def _loo_logistic(X: np.ndarray, y: np.ndarray, *, C: float = 0.5) -> dict[str, Any]:
    pred = []
    proba = []
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(max_iter=3000, class_weight="balanced", C=C)),
    ])
    for train, test in LeaveOneOut().split(X):
        model.fit(X[train], y[train])
        pred.append(int(model.predict(X[test])[0]))
        p = model.predict_proba(X[test])[0]
        classes = list(model.classes_)
        proba.append(float(p[classes.index(1)]) if 1 in classes else 0.5)
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "roc_auc": float(roc_auc_score(y, proba)),
    }


def _loo_residual_f2(X_f2: np.ndarray, X_conf: np.ndarray, y: np.ndarray, *, C: float = 0.5) -> dict[str, Any]:
    """Fit F2 residuals after confounders inside each LOO training fold."""

    pred = []
    proba = []
    for train, test in LeaveOneOut().split(X_f2):
        # Fit the confounder-adjustment on training only.
        reg = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LinearRegression()),
        ])
        reg.fit(X_conf[train], X_f2[train])
        train_resid = X_f2[train] - reg.predict(X_conf[train])
        test_resid = X_f2[test] - reg.predict(X_conf[test])
        clf = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=3000, class_weight="balanced", C=C)),
        ])
        clf.fit(train_resid, y[train])
        pred.append(int(clf.predict(test_resid)[0]))
        p = clf.predict_proba(test_resid)[0]
        classes = list(clf.classes_)
        proba.append(float(p[classes.index(1)]) if 1 in classes else 0.5)
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "roc_auc": float(roc_auc_score(y, proba)),
    }


def analyze(features_csv: Path, output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    y, Xd, ids, agents = _load(features_csv)
    X_f2 = np.column_stack([Xd[name] for name in F2])
    X_conf = np.column_stack([Xd[name] for name in CONFOUNDERS])
    X_all = np.column_stack([Xd[name] for name in F2 + CONFOUNDERS])

    correlations = []
    for f in F2:
        for c in CONFOUNDERS:
            rho, p = spearmanr(Xd[f], Xd[c])
            correlations.append({"feature": f, "confounder": c, "spearman_rho": float(rho), "p_value": float(p)})

    class_means = {}
    for agent in ("human", "game_bot"):
        idx = [i for i, value in enumerate(agents) if value == agent]
        class_means[agent] = {
            name: {
                "mean": float(np.mean([Xd[name][i] for i in idx])),
                "median": float(np.median([Xd[name][i] for i in idx])),
            }
            for name in F2 + CONFOUNDERS
        }

    models = {
        "f2_only": _loo_logistic(X_f2, y),
        "confounders_only": _loo_logistic(X_conf, y),
        "f2_plus_confounders": _loo_logistic(X_all, y),
        "f2_residualized": _loo_residual_f2(X_f2, X_conf, y),
    }
    result = {
        "schema_version": "anticheat.p0c_confounders.v1",
        "n_sessions": int(len(y)),
        "class_counts": {"human": int(np.sum(y == 0)), "game_bot": int(np.sum(y == 1))},
        "f2_features": F2,
        "confounders": CONFOUNDERS,
        "correlations": correlations,
        "class_means": class_means,
        "models": models,
    }
    (output_dir / "confounder_results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (output_dir / "correlations.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["feature", "confounder", "spearman_rho", "p_value"])
        writer.writeheader()
        writer.writerows(correlations)
    with (output_dir / "model_comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["model", "accuracy", "balanced_accuracy", "roc_auc"])
        writer.writeheader()
        for name, metrics in models.items():
            writer.writerow({"model": name, **metrics})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze P0-C F2 confounders")
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("runs/eval/anticheat_p0c/features_v2_v2/features_v2.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("runs/eval/anticheat_p0c/confounder_v1"))
    args = parser.parse_args(argv)
    try:
        result = analyze(args.features, args.output_dir)
    except Exception as exc:
        print(f"[ERROR] confounder analysis failed: {exc}", file=sys.stderr)
        return 2
    print(f"[INFO] confounder output: {args.output_dir} ({result['n_sessions']} sessions)")
    for name, metrics in result["models"].items():
        print(f"{name}: acc={metrics['accuracy']:.3f} bal={metrics['balanced_accuracy']:.3f} auc={metrics['roc_auc']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())