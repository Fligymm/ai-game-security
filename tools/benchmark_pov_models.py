"""Measure POV detector parameter count and single-image inference speed."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import torch

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from vision.detection.tiled_detector import TiledDetector
from vision.detection.yolo_detector import YOLODetector


def _sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark POV detectors")
    parser.add_argument("--models", type=Path, nargs="+", required=True)
    parser.add_argument("--images", type=Path, default=Path("datasets/pov_detection_v1/images/test"))
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--tile-size", type=int, default=720)
    parser.add_argument("--grid", type=int, default=3)
    parser.add_argument("--output", type=Path, default=Path("runs/eval/pov_speed.json"))
    args = parser.parse_args()
    images = sorted(args.images.glob("*.jpg"))[:80]
    loaded = [cv2.imread(str(path)) for path in images]
    results = []
    for model_path in args.models:
        full = YOLODetector(weights=model_path, conf=0.35, iou=0.5, imgsz=args.imgsz, device="0")
        params = sum(p.numel() for p in full.model.model.parameters())
        # warmup
        for image in loaded[:3]:
            full.detect_frame(image)
        _sync()
        start = time.perf_counter()
        for image in loaded:
            full.detect_frame(image)
        _sync()
        full_ms = (time.perf_counter() - start) * 1000 / len(loaded)
        tiled = TiledDetector(full, tile_size=args.tile_size, grid=args.grid)
        for image in loaded[:2]:
            tiled.detect_frame(image)
        _sync()
        start = time.perf_counter()
        for image in loaded:
            tiled.detect_frame(image)
        _sync()
        tiled_ms = (time.perf_counter() - start) * 1000 / len(loaded)
        results.append({
            "model": str(model_path),
            "params_m": round(params / 1e6, 3),
            "full_frame_ms": round(full_ms, 2),
            "full_frame_fps": round(1000 / full_ms, 1),
            "tiled_ms": round(tiled_ms, 2),
            "tiled_fps": round(1000 / tiled_ms, 1),
        })
        print(json.dumps(results[-1], indent=2))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())