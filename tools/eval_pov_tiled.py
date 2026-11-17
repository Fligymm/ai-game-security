"""Evaluate tiled inference on the reviewed POV test split (micro P/R)."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2

_REPO = Path(__file__).resolve().parents[1]
import sys
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from vision.detection.tiled_detector import TiledDetector
from vision.detection.yolo_detector import YOLODetector


def _read_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 5:
            rows.append((int(parts[0]), *(float(value) for value in parts[1:])))
    return rows


def _iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    return inter / (area_a + area_b - inter) if area_a + area_b - inter > 0 else 0.0


def micro_pr(images: list[Path], labels_dir: Path, weights: Path, tile_size: int, grid: int, imgsz: int, conf: float) -> dict:
    detector = TiledDetector(
        YOLODetector(weights=weights, conf=conf, iou=0.5, imgsz=imgsz, device="0"),
        tile_size=tile_size,
        grid=grid,
    )
    stats = {0: {"tp": 0, "fp": 0, "fn": 0}, 1: {"tp": 0, "fp": 0, "fn": 0}}
    for image_path in images:
        image = cv2.imread(str(image_path))
        h, w = image.shape[:2]
        detections = detector.detect_frame(image)
        gt = []
        for cid, cx, cy, bw, bh in _read_labels(labels_dir / f"{image_path.stem}.txt"):
            gt.append((cid, (cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h))
        used = set()
        for det in sorted(detections, key=lambda d: d.conf, reverse=True):
            candidates = [
                (index, _iou((det.x1, det.y1, det.x2, det.y2), box))
                for index, (cid, *box) in enumerate(gt)
                if cid == det.cls_id and index not in used
            ]
            if candidates:
                index, iou = max(candidates, key=lambda item: item[1])
                if iou >= 0.5:
                    used.add(index)
                    stats[int(det.cls_id)]["tp"] += 1
                    continue
            stats[int(det.cls_id)]["fp"] += 1
        for index, (cid, *_) in enumerate(gt):
            if index not in used:
                stats[cid]["fn"] += 1
    result = {}
    for cid, name in ((0, "enemy_head"), (1, "enemy_body")):
        tp, fp, fn = stats[cid]["tp"], stats[cid]["fp"], stats[cid]["fn"]
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        result[name] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Tiled micro P/R on POV test")
    parser.add_argument("--models", type=Path, nargs="+", required=True)
    parser.add_argument("--images", type=Path, default=Path("datasets/pov_detection_v1/images/test"))
    parser.add_argument("--labels", type=Path, default=Path("datasets/pov_detection_v1/labels/test"))
    parser.add_argument("--tile-size", type=int, default=720)
    parser.add_argument("--grid", type=int, default=3)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--output", type=Path, default=Path("runs/eval/pov_tiled_eval.json"))
    args = parser.parse_args()
    images = sorted(args.images.glob("*.jpg"))
    results = []
    for model in args.models:
        result = micro_pr(images, args.labels, model, args.tile_size, args.grid, args.imgsz, args.conf)
        results.append({"model": str(model), **result})
        print(json.dumps(results[-1], indent=2))
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())