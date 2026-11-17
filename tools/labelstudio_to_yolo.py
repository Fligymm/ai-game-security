"""Convert a Label Studio JSON export into YOLO labels for the POV test set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CLASS_IDS = {"enemy_head": 0, "enemy_body": 1}


def _load_tasks(export_path: Path) -> list[dict]:
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    tasks = payload if isinstance(payload, list) else payload.get("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("Label Studio export must be a task list")
    return tasks


def _task_filename(task: dict) -> str | None:
    data = task.get("data") or {}
    for value in (data.get("image"), data.get("file_upload"), data.get("image_url"), task.get("file_upload")):
        if isinstance(value, str):
            return Path(value.split("?")[0]).name
    return None


def _chosen_annotation(task: dict) -> dict | None:
    annotations = [a for a in task.get("annotations") or [] if not a.get("was_cancelled")]
    if not annotations:
        return None
    return max(annotations, key=lambda a: (str(a.get("updated_at") or ""), int(a.get("id") or 0)))


def _filename(task: dict) -> str | None:
    return _task_filename(task)


def _resolve_image(name: str, images: set[str]) -> tuple[str | None, list[str]]:
    if name in images:
        return name, [name]
    candidates = [image for image in images if image.endswith(name) or name.endswith(image)]
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates


def convert(export_path: Path, images_dir: Path, labels_dir: Path) -> dict:
    tasks = _load_tasks(export_path)
    labels_dir.mkdir(parents=True, exist_ok=True)
    images = {path.name for path in images_dir.glob("*") if path.is_file()}
    written = []
    errors = []
    boxes_total = 0
    seen_images: set[str] = set()
    for task in tasks:
        upload_name = _filename(task)
        if not upload_name:
            errors.append("task missing image filename")
            continue
        name, candidates = _resolve_image(upload_name, images)
        if name is None:
            errors.append(f"cannot resolve image for task: {upload_name!r} candidates={candidates}")
            continue
        seen_images.add(name)
        annotation = _chosen_annotation(task)
        results = (annotation.get("result") or []) if annotation else []
        labels = []
        for result in results:
            if result.get("type") != "rectanglelabels":
                continue
            value = result.get("value") or {}
            names = value.get("rectanglelabels") or []
            if not names or names[0] not in CLASS_IDS:
                errors.append(f"{name}: unknown label {names}")
                continue
            x = float(value.get("x", 0.0))
            y = float(value.get("y", 0.0))
            w = float(value.get("width", 0.0))
            h = float(value.get("height", 0.0))
            if not (0.0 <= x <= 100.0 and 0.0 <= y <= 100.0 and 0.0 < w <= 100.0 and 0.0 < h <= 100.0):
                errors.append(f"{name}: invalid normalized rectangle")
                continue
            cx = (x + w / 2.0) / 100.0
            cy = (y + h / 2.0) / 100.0
            bw = w / 100.0
            bh = h / 100.0
            labels.append(f"{CLASS_IDS[names[0]]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            boxes_total += 1
        path = labels_dir / f"{Path(name).stem}.txt"
        path.write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")
        written.append({"image": name, "label": path.name, "boxes": len(labels)})
    missing = sorted(images - seen_images)
    for name in missing:
        errors.append(f"no Label Studio task for image: {name}")
    return {
        "ok": not errors,
        "written": written,
        "boxes": boxes_total,
        "missing": missing,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert Label Studio JSON to YOLO")
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--images", type=Path, default=Path("datasets/pov_detection_v1/images/test"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path, default=None)
    args = parser.parse_args(argv)
    result = convert(args.export, args.images, args.output_dir)
    text = json.dumps({**result, "count": len(result["written"])}, indent=2, ensure_ascii=False)
    print(text)
    if args.summary:
        args.summary.write_text(text, encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())