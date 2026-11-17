"""Evaluate POV detectors on the reviewed test split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[1]


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else _REPO / path


def evaluate(model_path: Path, data_path: Path, imgsz: int, conf: float, iou: float, split: str) -> dict:
    from ultralytics import YOLO

    model = YOLO(str(model_path))
    metrics = model.val(
        data=str(data_path),
        split=split,
        imgsz=imgsz,
        conf=conf,
        iou=iou,
        plots=False,
        verbose=False,
    )
    box = metrics.box
    names = getattr(metrics, "names", {}) or {}
    per_class = {}
    indices = getattr(box, "ap_class_index", [])
    indices = [] if indices is None else list(indices)
    for index, class_id in enumerate(indices):
        try:
            cid = int(class_id)
            precision, recall, ap50, ap = box.class_result(index)
            per_class[names.get(cid, str(cid))] = {
                "mAP50-95": float(ap),
                "mAP50": float(ap50),
                "precision": float(precision),
                "recall": float(recall),
            }
        except (IndexError, TypeError, ValueError):
            continue
    return {
        "model": str(model_path),
        "imgsz": imgsz,
        "conf": conf,
        "iou": iou,
        "split": split,
        "mAP50-95": float(box.map),
        "mAP50": float(box.map50),
        "mAP75": float(box.map75),
        "precision": float(box.mp),
        "recall": float(box.mr),
        "per_class": per_class,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate POV detectors")
    parser.add_argument("--data", type=Path, default=Path("datasets/pov_detection_v1/data.yaml"))
    parser.add_argument("--models", type=Path, nargs="+", required=True)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--split", default="test")
    parser.add_argument("--output", type=Path, default=Path("runs/eval/pov_detection_eval.json"))
    args = parser.parse_args()
    data_path = _resolve(args.data)
    payload = yaml.safe_load(data_path.read_text(encoding="utf-8"))
    payload["path"] = str(data_path.parent.resolve())
    resolved = args.output.parent / "data_eval_resolved.yaml"
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    results = []
    for model in args.models:
        model_path = _resolve(model)
        results.append(evaluate(model_path, resolved, args.imgsz, args.conf, args.iou, args.split))
        print(json.dumps(results[-1], indent=2, ensure_ascii=False))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())