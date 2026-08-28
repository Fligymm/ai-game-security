"""Train a YOLOv8n detector on datasets/cs2_custom (Ultralytics).

Uses data.yaml class definitions as-is (0=enemy_head, 1=enemy_body).
Does not modify vision.detection.YOLODetector.
"""

from __future__ import annotations

from pathlib import Path

from ultralytics import YOLO

_REPO_ROOT = Path(__file__).resolve().parent
_DATASET_ROOT = _REPO_ROOT / "datasets" / "cs2_custom"
_DATA_YAML = _DATASET_ROOT / "data.yaml"
_WEIGHTS = "yolov8n.pt"


def _rewrite_data_yaml() -> Path:
    """Write an absolute dataset `path` so Ultralytics does not join train/val
    against the process cwd (which produced missing <repo>/val/images).
    Class ids stay frozen.
    """
    root = _DATASET_ROOT.resolve()
    train_images = root / "train" / "images"
    val_images = root / "val" / "images"
    if not train_images.is_dir() or not val_images.is_dir():
        raise FileNotFoundError(
            "train/val image folders missing. Run "
            "python behavior/collection/split_dataset.py first.\n"
            f"  {train_images}\n  {val_images}"
        )
    n_train = sum(1 for p in train_images.iterdir() if p.is_file() and p.name != ".gitkeep")
    n_val = sum(1 for p in val_images.iterdir() if p.is_file() and p.name != ".gitkeep")
    if n_train == 0 or n_val == 0:
        raise FileNotFoundError(
            f"empty split: train_images={n_train} val={n_val}. "
            "Re-run python behavior/collection/split_dataset.py"
        )

    _DATA_YAML.write_text(
        (
            "# Auto-resolved by train.py — do not set path to '.'\n"
            "# Classes frozen: 0 enemy_head, 1 enemy_body\n"
            f"path: {root.as_posix()}\n"
            "train: train/images\n"
            "val: val/images\n"
            "\n"
            "nc: 2\n"
            "names:\n"
            "  0: enemy_head\n"
            "  1: enemy_body\n"
        ),
        encoding="utf-8",
    )
    print(f"data.yaml   : {_DATA_YAML}")
    print(f"dataset root: {root}")
    print(f"train images: {n_train}")
    print(f"val images  : {n_val}")
    return _DATA_YAML


def main() -> None:
    data_yaml = _rewrite_data_yaml()
    model = YOLO(_WEIGHTS)
    model.train(
        data=str(data_yaml),
        epochs=50,
        imgsz=640,
        batch=16,
        device=0,
        project=str(_REPO_ROOT / "runs" / "detect"),
        name="cs2_detection_v1",
        exist_ok=True,
        workers=2,
    )


if __name__ == "__main__":
    main()
