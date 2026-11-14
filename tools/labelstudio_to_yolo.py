"""Convert a Label Studio JSON export to YOLO labels for the pilot sample."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote

CLASS_IDS = {"enemy_head": 0, "enemy_body": 1}


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("tasks"), list):
        return payload["tasks"]
    raise ValueError("export must be a Label Studio JSON list or {'tasks': [...]}")


def _task_filename(task: dict[str, Any]) -> str | None:
    for key in ("file_upload", "image"):
        value = task.get(key)
        if value is None:
            value = (task.get("data") or {}).get(key)
        if value:
            return Path(unquote(str(value))).name
    return None


def _chosen_annotation(task: dict[str, Any]) -> dict[str, Any] | None:
    annotations = task.get("annotations") or []
    if not isinstance(annotations, list) or not annotations:
        return None
    for annotation in reversed(annotations):
        if not annotation.get("was_cancelled"):
            return annotation
    return None


def _yolo_line(result: dict[str, Any]) -> str | None:
    if result.get("type") != "rectanglelabels":
        return None
    value = result.get("value") or {}
    labels = value.get("rectanglelabels") or []
    if not labels:
        return None
    name = str(labels[0])
    if name not in CLASS_IDS:
        raise ValueError(f"unknown label {name!r}; expected {sorted(CLASS_IDS)}")
    try:
        x = float(value["x"]) / 100.0
        y = float(value["y"]) / 100.0
        width = float(value["width"]) / 100.0
        height = float(value["height"]) / 100.0
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"bad rectangle value: {value!r}") from exc
    if width <= 0 or height <= 0:
        raise ValueError(f"non-positive rectangle size: {value!r}")
    x1 = max(0.0, min(1.0, x))
    y1 = max(0.0, min(1.0, y))
    x2 = max(x1, min(1.0, x + width))
    y2 = max(y1, min(1.0, y + height))
    return (
        f"{CLASS_IDS[name]} "
        f"{(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} "
        f"{x2 - x1:.6f} {y2 - y1:.6f}"
    )


def convert(
    export_path: Path,
    images_dir: Path,
    labels_dir: Path,
    *,
    allow_missing: bool = False,
) -> dict[str, Any]:
    tasks = _load_tasks(export_path)
    images = {path.name: path for path in images_dir.glob("*.jpg")}
    labels_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    boxes = 0
    empty = 0

    for task in tasks:
        filename = _task_filename(task)
        if not filename:
            errors.append("task without file_upload/image")
            continue
        # Label Studio uploads may prepend an 8-hex-character prefix to the
        # stored filename (e.g. "3955725a-static_target...jpg").  Accept an
        # unambiguous match where either name is the suffix of the other.
        resolved = filename if filename in images else None
        if resolved is None:
            candidates = [
                name
                for name in images
                if name.endswith(filename) or filename.endswith(name)
            ]
            if len(candidates) == 1:
                resolved = candidates[0]
        if resolved is None:
            errors.append(f"image not found for task: {filename}")
            continue
        if resolved in seen:
            errors.append(f"duplicate task for image: {resolved}")
            continue
        seen.add(resolved)

        annotation = _chosen_annotation(task)
        if annotation is None:
            errors.append(f"no completed annotation: {resolved}")
            continue

        lines: list[str] = []
        for result in annotation.get("result") or []:
            try:
                line = _yolo_line(result)
            except ValueError as exc:
                errors.append(f"{resolved}: {exc}")
                continue
            if line:
                lines.append(line)
        label_path = labels_dir / f"{Path(resolved).stem}.txt"
        label_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        boxes += len(lines)
        empty += int(not lines)

    missing = sorted(set(images) - seen)
    if missing:
        message = (
            f"{len(missing)} images have no Label Studio task; "
            "if they are empty, Submit an empty annotation instead of Skip"
        )
        if allow_missing:
            warnings.append(message)
        else:
            errors.append(message)

    return {
        "ok": not errors,
        "export": str(export_path),
        "images": len(images),
        "labeled_tasks": len(seen),
        "missing": missing,
        "boxes": boxes,
        "empty_labels": empty,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Label Studio JSON to YOLO labels")
    parser.add_argument("--export", type=Path, required=True, help="Label Studio JSON export")
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--labels-dir", type=Path, required=True)
    parser.add_argument("--allow-missing", action="store_true", help="Do not fail when images are not in the export")
    args = parser.parse_args()

    report = convert(
        args.export,
        args.images_dir,
        args.labels_dir,
        allow_missing=args.allow_missing,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()