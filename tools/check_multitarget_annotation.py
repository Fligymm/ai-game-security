"""Validate a multi-target annotation sample before training."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import cv2

CLASS_NAMES = {0: "enemy_head", 1: "enemy_body"}


def _validate_label(path: Path) -> tuple[list[tuple[int, float, float, float, float]], list[str]]:
    boxes: list[tuple[int, float, float, float, float]] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5:
            errors.append(f"{path.name}:{line_number}: expected 5 fields, got {len(parts)}")
            continue
        try:
            class_id = int(parts[0])
            values = [float(value) for value in parts[1:]]
        except ValueError:
            errors.append(f"{path.name}:{line_number}: non-numeric value")
            continue
        if class_id not in CLASS_NAMES:
            errors.append(f"{path.name}:{line_number}: class_id={class_id} not in {CLASS_NAMES}")
            continue
        xc, yc, width, height = values
        if not all(0.0 <= value <= 1.0 for value in values):
            errors.append(f"{path.name}:{line_number}: normalized coords outside 0..1")
            continue
        if width <= 0 or height <= 0:
            errors.append(f"{path.name}:{line_number}: non-positive width/height")
            continue
        boxes.append((class_id, xc, yc, width, height))
    return boxes, errors


def check(
    annotation_root: Path,
    *,
    min_frames: int = 150,
    min_multi: int = 60,
    min_empty: int = 20,
) -> dict[str, Any]:
    manifest_path = annotation_root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest.get("items", [])
    errors: list[str] = []
    warnings: list[str] = []
    class_counts: Counter[str] = Counter()
    per_scene: dict[str, Counter[str]] = {}
    multi_frames = 0
    empty_frames = 0
    images = 0

    for item in items:
        image_path = annotation_root / item["image"]
        label_path = annotation_root / item["label"]
        if not image_path.is_file():
            errors.append(f"missing image: {item['image']}")
        elif cv2.imread(str(image_path)) is None:
            errors.append(f"cannot decode image: {item['image']}")
        else:
            images += 1
        if not label_path.is_file():
            errors.append(f"missing label: {item['label']}")
            continue
        boxes, label_errors = _validate_label(label_path)
        errors.extend(label_errors)
        heads = sum(1 for box in boxes if box[0] == 0)
        if not boxes:
            empty_frames += 1
        if heads >= 2:
            multi_frames += 1
        for box in boxes:
            class_counts[CLASS_NAMES[box[0]]] += 1
        scene = str(item.get("scene", "unknown"))
        per_scene.setdefault(scene, Counter())
        per_scene[scene][CLASS_NAMES[0]] += heads
        per_scene[scene][CLASS_NAMES[1]] += sum(1 for box in boxes if box[0] == 1)

    if len(items) < min_frames:
        errors.append(f"frames={len(items)} < {min_frames}")
    if images != len(items):
        errors.append(f"decodable images={images} != frames={len(items)}")
    if multi_frames < min_multi:
        errors.append(f"multi-target frames={multi_frames} < {min_multi}")
    if empty_frames < min_empty:
        errors.append(f"empty frames={empty_frames} < {min_empty}")
    scenes = sorted(per_scene)
    if len(scenes) < 3:
        warnings.append(f"only {len(scenes)} scenes: {scenes}")
    if len(items) and not any(item.get("scene") == "fast_strafe" for item in items):
        warnings.append("fast_strafe missing")

    report = {
        "ok": not errors,
        "annotation_root": str(annotation_root),
        "frames": len(items),
        "decodable_images": images,
        "multi_target_frames": multi_frames,
        "empty_frames": empty_frames,
        "class_counts": dict(class_counts),
        "by_scene": {scene: dict(counter) for scene, counter in sorted(per_scene.items())},
        "scenes": scenes,
        "sessions": sorted({str(item.get("session_id")) for item in items}),
        "requirements": {
            "min_frames": min_frames,
            "min_multi": min_multi,
            "min_empty": min_empty,
        },
        "errors": errors,
        "warnings": warnings,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate multi-target annotation sample")
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--min-frames", type=int, default=150)
    parser.add_argument("--min-multi", type=int, default=60)
    parser.add_argument("--min-empty", type=int, default=20)
    args = parser.parse_args()
    report = check(
        args.annotation,
        min_frames=args.min_frames,
        min_multi=args.min_multi,
        min_empty=args.min_empty,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()