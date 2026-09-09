"""Plot key trajectory-feature distributions for offline research datasets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DATASET_NAMES = ("human", "bot_agent", "synthetic")
FEATURES = (
    "acceleration_rms",
    "jerk_mean",
    "jerk_rms",
    "zero_speed_fraction",
)
COLORS = ("#2a9d8f", "#e76f51", "#457b9d")


def load_feature_distributions(data_root: str | Path = "datasets") -> dict[str, dict[str, list[float]]]:
    """Load finite values from each dataset's exported ``features.json``."""
    root = Path(data_root)
    distributions: dict[str, dict[str, list[float]]] = {}
    for dataset_name in DATASET_NAMES:
        path = root / dataset_name / "features.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected an object in {path}")
        values = {feature: [] for feature in FEATURES}
        for record in payload.values():
            if not isinstance(record, dict):
                continue
            for feature in FEATURES:
                value = record.get(feature)
                if isinstance(value, bool):
                    value = float(value)
                if isinstance(value, (int, float)) and np.isfinite(value):
                    values[feature].append(float(value))
        distributions[dataset_name] = values
    if not distributions:
        raise FileNotFoundError(f"no dataset features found below {root}")
    return distributions


def plot_feature_distributions(
    data_root: str | Path = "datasets",
    output_path: str | Path | None = None,
) -> Path:
    """Create and save the 2x2 feature comparison figure."""
    root = Path(data_root)
    output = Path(output_path) if output_path is not None else root / "feature_distribution_comparison.png"
    distributions = load_feature_distributions(root)
    available = [name for name in DATASET_NAMES if name in distributions]
    if not available:
        raise ValueError("no supported dataset contains feature values")

    figure, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)
    for axis, feature in zip(axes.flat, FEATURES):
        plotted = []
        labels = []
        colors = []
        for dataset_name in available:
            values = distributions[dataset_name][feature]
            if values:
                plotted.append(values)
                labels.append(dataset_name)
                colors.append(COLORS[DATASET_NAMES.index(dataset_name)])
        if plotted:
            box = axis.boxplot(plotted, tick_labels=labels, patch_artist=True, showfliers=False)
            for patch, color in zip(box["boxes"], colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.72)
            axis.set_yscale("symlog", linthresh=1.0) if feature != "zero_speed_fraction" else None
        else:
            axis.text(0.5, 0.5, "No finite samples", ha="center", va="center", transform=axis.transAxes)
        axis.set_title(feature)
        axis.set_ylabel("Value")
        axis.grid(axis="y", alpha=0.25)

    figure.suptitle("Trajectory Feature Distribution Comparison", fontsize=15)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=160, format="png")
    plt.close(figure)
    print(f"[INFO] Feature distribution plot saved to {output}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot offline trajectory feature distributions")
    parser.add_argument("--data-root", type=Path, default=Path("datasets"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    plot_feature_distributions(args.data_root, args.output)


if __name__ == "__main__":
    main()
