"""Validate YOLO labels for the POV detection benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def validate(images_dir: Path, labels_dir: Path) -> dict:
    images = sorted(p for p in images_dir.iterdir() if p.is_file())
    labels = sorted(p for p in labels_dir.iterdir() if p.suffix == ".txt")
    image_stems = {p.stem for p in images}
    label_stems = {p.stem for p in labels}
    errors: list[str] = []
    counts = {"images": len(images), "labels": len(labels), "boxes": 0, "empty": 0, "head": 0, "body": 0}
    missing_labels = sorted(image_stems - label_stems)
    missing_images = sorted(label_stems - image_stems)
    if missing_labels:
        errors.append(f"images without labels: {len(missing_labels)}")
    if missing_images:
        errors.append(f"labels without images: {len(missing_images)}")
    for label_path in labels:
        seen: set[tuple[str, str, str, str]] = set()
        lines = [line.strip() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            counts["empty"] += 1
            continue
        for line_number, line in enumerate(lines, 1):
            parts = line.split()
            if len(parts) != 5:
                errors.append(f"{label_path.name}:{line_number}: expected 5 fields")
                continue
            try:
                class_id = int(parts[0])
                cx, cy, bw, bh = (float(value) for value in parts[1:])
            except ValueError:
                errors.append(f"{label_path.name}:{line_number}: non-numeric field")
                continue
            if class_id not in (0, 1):
                errors.append(f"{label_path.name}:{line_number}: class must be 0 or 1")
            if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0 and 0.0 < bw <= 1.0 and 0.0 < bh <= 1.0):
                errors.append(f"{label_path.name}:{line_number}: coordinate outside (0,1]")
            key = (str(class_id), parts[1], parts[2], parts[3])
            if key in seen:
                errors.append(f"{label_path.name}:{line_number}: duplicate box")
            seen.add(key)
            counts["boxes"] += 1
            counts["head" if class_id == 0 else "body"] += 1
    return {
        "ok": not errors,
        "counts": counts,
        "missing_labels": missing_labels[:20],
        "missing_images": missing_images[:20],
        "errors": errors[:40],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate POV YOLO labels")
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    result = validate(args.images, args.labels)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())