"""Evaluate a detector on the manually labeled pilot sample.

This is an external test: the 90 frames are not used for training.  It reports
Ultralytics mAP for both classes, plus per-scene precision/recall at the
deployment confidence (default 0.35) and false positives on empty frames.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np
from ultralytics import YOLO

CLASS_NAMES = {0: "enemy_head", 1: "enemy_body"}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_label(path: Path, width: int, height: int) -> list[dict[str, Any]]:
    boxes: list[dict[str, Any]] = []
    if not path.is_file():
        raise FileNotFoundError(path)
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"{path}:{line_no}: expected 5 values")
        cls, xc, yc, bw, bh = float(parts[0]), *map(float, parts[1:])
        if cls not in CLASS_NAMES:
            raise ValueError(f"{path}:{line_no}: unknown class {cls}")
        if not all(0.0 <= value <= 1.0 for value in (xc, yc, bw, bh)) or bw <= 0 or bh <= 0:
            raise ValueError(f"{path}:{line_no}: invalid normalized box")
        x1 = (xc - bw / 2) * width
        y1 = (yc - bh / 2) * height
        x2 = (xc + bw / 2) * width
        y2 = (yc + bh / 2) * height
        boxes.append({"class_id": int(cls), "xyxy": [x1, y1, x2, y2]})
    return boxes


def _iou(a: Iterable[float], b: Iterable[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return float(inter / (area_a + area_b - inter))


def _match_image(
    truth: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    iou_threshold: float,
) -> dict[str, int]:
    """Greedy per-class matching; returns TP/FP/FN over all classes."""

    tp = fp = fn = 0
    for class_id in CLASS_NAMES:
        gt = [box for box in truth if box["class_id"] == class_id]
        preds = sorted(
            [box for box in predictions if box["class_id"] == class_id],
            key=lambda box: box["confidence"],
            reverse=True,
        )
        used: set[int] = set()
        for pred in preds:
            best_index, best_iou = None, 0.0
            for index, box in enumerate(gt):
                if index in used:
                    continue
                overlap = _iou(box["xyxy"], pred["xyxy"])
                if overlap > best_iou:
                    best_index, best_iou = index, overlap
            if best_index is not None and best_iou >= iou_threshold:
                used.add(best_index)
                tp += 1
            else:
                fp += 1
        fn += len(gt) - len(used)
    return {"tp": tp, "fp": fp, "fn": fn}


def _prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _metric_value(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    return value


def _val_summary(metrics: Any) -> dict[str, Any]:
    box = metrics.box
    names = {int(k): str(v) for k, v in metrics.names.items()}
    per_class: dict[str, Any] = {}
    for index, name in names.items():
        try:
            per_class[name] = {
                "precision": float(box.p[index]),
                "recall": float(box.r[index]),
                "ap50": float(box.ap50[index]),
                "ap50_95": float(box.ap[index]),
            }
        except (IndexError, TypeError):
            per_class[name] = None
    return {
        "results": {key: _metric_value(value) for key, value in metrics.results_dict.items()},
        "per_class": per_class,
    }


def _prepare_scene_dataset(
    annotation_root: Path,
    output_root: Path,
    scene: str,
    items: list[dict[str, Any]],
) -> Path:
    scene_root = output_root / "scene_data" / scene
    images_dir = scene_root / "images"
    labels_dir = scene_root / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    for item in items:
        image_src = annotation_root / item["image"]
        label_src = annotation_root / item["label"]
        shutil.copy2(image_src, images_dir / image_src.name)
        shutil.copy2(label_src, labels_dir / label_src.name)
    data_path = scene_root / "data.yaml"
    data_path.write_text(
        "\n".join(
            [
                f"path: {scene_root.as_posix()}",
                "train: images",
                "val: images",
                "",
                "nc: 2",
                "names:",
                "  0: enemy_head",
                "  1: enemy_body",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return data_path


def evaluate(
    model_path: Path,
    annotation_root: Path,
    output_root: Path,
    *,
    imgsz: int = 640,
    val_conf: float = 0.001,
    deployment_conf: float = 0.35,
    iou_threshold: float = 0.5,
    device: str = "0",
    workers: int = 0,
    batch: int = 16,
) -> dict[str, Any]:
    manifest_path = annotation_root / "manifest.json"
    manifest = _read_json(manifest_path)
    items = manifest["items"]
    labels_dir = annotation_root / "labels"

    errors: list[str] = []
    for item in items:
        image_path = annotation_root / item["image"]
        label_path = annotation_root / item["label"]
        if not image_path.is_file():
            errors.append(f"missing image: {image_path}")
            continue
        if not label_path.is_file():
            errors.append(f"missing label: {label_path}")
            continue
        image = cv2.imread(str(image_path))
        if image is None:
            errors.append(f"cannot decode: {image_path}")
            continue
        try:
            _read_label(label_path, image.shape[1], image.shape[0])
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))
    if errors:
        return {"ok": False, "errors": errors, "warnings": []}

    output_root.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(model_path))

    overall_data = annotation_root / "data.yaml"
    overall = model.val(
        data=str(overall_data),
        split="val",
        imgsz=imgsz,
        conf=val_conf,
        iou=0.7,
        batch=batch,
        device=device,
        workers=workers,
        project=str(output_root),
        name="overall",
        exist_ok=True,
        plots=False,
        verbose=False,
    )

    by_scene: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_scene.setdefault(str(item["scene"]), []).append(item)

    per_scene_val: dict[str, Any] = {}
    for scene, scene_items in sorted(by_scene.items()):
        data_path = _prepare_scene_dataset(annotation_root, output_root, scene, scene_items)
        metrics = model.val(
            data=str(data_path),
            split="val",
            imgsz=imgsz,
            conf=val_conf,
            iou=0.7,
            batch=batch,
            device=device,
            workers=workers,
            project=str(output_root),
            name=f"scene_{scene}",
            exist_ok=True,
            plots=False,
            verbose=False,
        )
        per_scene_val[scene] = _val_summary(metrics)

    # Deployment-threshold matching, per image and per scene.
    deployment: dict[str, Any] = {"all": {}, "head_only": {}}
    for mode, classes in (("all", {0, 1}), ("head_only", {0})):
        totals = {"images": 0, "gt": 0, "pred": 0, "tp": 0, "fp": 0, "fn": 0}
        per_scene: dict[str, dict[str, int]] = {}
        empty = {"images": 0, "with_prediction": 0, "boxes": 0}
        for item in items:
            scene = str(item["scene"])
            image_path = annotation_root / item["image"]
            label_path = annotation_root / item["label"]
            image = cv2.imread(str(image_path))
            truth = _read_label(label_path, image.shape[1], image.shape[0])
            result = model.predict(
                source=image,
                imgsz=imgsz,
                conf=deployment_conf,
                iou=0.7,
                device=device,
                verbose=False,
                max_det=300,
            )[0]
            predictions: list[dict[str, Any]] = []
            if result.boxes is not None and len(result.boxes):
                for xyxy, confidence, class_id in zip(
                    result.boxes.xyxy.cpu().numpy(),
                    result.boxes.conf.cpu().numpy(),
                    result.boxes.cls.cpu().numpy(),
                ):
                    class_id = int(class_id)
                    if class_id in classes:
                        predictions.append(
                            {
                                "xyxy": [float(v) for v in xyxy],
                                "confidence": float(confidence),
                                "class_id": class_id,
                            }
                        )
            truth_eval = [box for box in truth if box["class_id"] in classes]
            matched = _match_image(truth_eval, predictions, iou_threshold)
            stats = per_scene.setdefault(
                scene,
                {"images": 0, "gt": 0, "pred": 0, "tp": 0, "fp": 0, "fn": 0},
            )
            gt_count = len(truth_eval)
            stats["images"] += 1
            stats["gt"] += gt_count
            stats["pred"] += len(predictions)
            stats["tp"] += matched["tp"]
            stats["fp"] += matched["fp"]
            stats["fn"] += matched["fn"]
            totals["images"] += 1
            totals["gt"] += gt_count
            totals["pred"] += len(predictions)
            totals["tp"] += matched["tp"]
            totals["fp"] += matched["fp"]
            totals["fn"] += matched["fn"]
            if not truth:
                empty["images"] += 1
                if predictions:
                    empty["with_prediction"] += 1
                    empty["boxes"] += len(predictions)

        for stats in per_scene.values():
            stats.update(_prf(stats["tp"], stats["fp"], stats["fn"]))
        totals.update(_prf(totals["tp"], totals["fp"], totals["fn"]))
        deployment[mode] = {
            "overall": totals,
            "per_scene": per_scene,
            "empty_frames": empty,
        }

    report = {
        "ok": True,
        "model": str(model_path),
        "annotation_root": str(annotation_root),
        "imgsz": imgsz,
        "val_conf": val_conf,
        "deployment_conf": deployment_conf,
        "iou_threshold": iou_threshold,
        "overall_val": _val_summary(overall),
        "per_scene_val": per_scene_val,
        "deployment": deployment,
        "counts": {
            "images": len(items),
            "empty_labels": sum(
                1
                for item in items
                if not (annotation_root / item["label"]).read_text(encoding="utf-8").strip()
            ),
        },
        "errors": [],
        "warnings": [],
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate YOLO on the labeled pilot sample")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--val-conf", type=float, default=0.001)
    parser.add_argument("--deployment-conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--batch", type=int, default=16)
    args = parser.parse_args()

    report = evaluate(
        args.model,
        args.annotation,
        args.output,
        imgsz=args.imgsz,
        val_conf=args.val_conf,
        deployment_conf=args.deployment_conf,
        iou_threshold=args.iou,
        device=args.device,
        workers=args.workers,
        batch=args.batch,
    )
    output_path = args.output / "eval_report.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()