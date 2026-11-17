"""Train a POV-adapted YOLOv8n detector.

Safety default: dry-run. Pass ``--execute`` to start training.
Test labels are the reviewed human labels; train/val labels are prelabels.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train POV-adapted YOLOv8n")
    parser.add_argument("--data", type=Path, default=Path("datasets/pov_detection_v1/data.yaml"))
    parser.add_argument("--weights", type=Path, default=Path("runs/detect/cs2_detection_v2/weights/best.pt"))
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--patience", type=int, default=15)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--project", type=Path, default=Path("runs/detect"))
    parser.add_argument("--name", default="pov_ft_v1")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    data_path = args.data if args.data.is_absolute() else _REPO / args.data
    weights = args.weights if args.weights.is_absolute() else _REPO / args.weights
    project = args.project if args.project.is_absolute() else _REPO / args.project
    if not data_path.exists():
        print(f"[ERROR] data yaml not found: {data_path}", file=sys.stderr)
        return 2
    if not weights.exists():
        print(f"[ERROR] weights not found: {weights}", file=sys.stderr)
        return 2
    payload = yaml.safe_load(data_path.read_text(encoding="utf-8"))
    payload["path"] = str(data_path.parent.resolve())
    resolved = project / args.name / "data_resolved.yaml"
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    command = {
        "data": str(resolved),
        "weights": str(weights),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
        "project": str(project),
        "name": args.name,
        "execute": args.execute,
    }
    print(json.dumps(command, indent=2))
    if not args.execute:
        print("[INFO] dry-run only; pass --execute to train")
        return 0

    from ultralytics import YOLO

    model = YOLO(str(weights))
    model.train(
        data=str(resolved),
        epochs=args.epochs,
        patience=args.patience,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(project),
        name=args.name,
        exist_ok=False,
        seed=42,
        deterministic=True,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        warmup_epochs=1.0,
        weight_decay=0.0005,
        cos_lr=True,
        close_mosaic=10,
        mosaic=0.5,
        mixup=0.0,
        copy_paste=0.0,
        degrees=0.0,
        translate=0.1,
        scale=0.3,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.5,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        amp=True,
        val=True,
        plots=True,
        save=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())