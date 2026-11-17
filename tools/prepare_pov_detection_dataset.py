"""Build a small POV detection benchmark from existing tiled inference outputs.

The output labels are PRELABELS produced by the old model. They are intended for
manual review/correction before training. This tool does not train a model or
modify existing sessions.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "sessions" not in payload:
        raise ValueError("config missing sessions")
    return payload


def _sample(records: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    selected = [row for row in records if isinstance(row.get("selected"), dict)]
    detected = [row for row in records if row.get("detections")]
    empty = [row for row in records if not row.get("detections")]
    picks: list[dict[str, Any]] = []
    seen: set[int] = set()

    def take(pool: list[dict[str, Any]], target: int) -> None:
        if target <= 0 or not pool:
            return
        step = max(1, len(pool) // target)
        for row in pool[::step]:
            frame = int(row.get("frame_index", 0))
            if frame in seen:
                continue
            picks.append(row)
            seen.add(frame)
            if len(picks) >= count:
                return

    take(selected, max(1, count // 2))
    take(detected, max(1, count // 4))
    take(empty, max(1, count // 4))
    if len(picks) < count:
        take(detected + selected + empty, count - len(picks))
    return picks[:count]


def _boxes(record: dict[str, Any], min_conf: float, max_detections: int) -> list[tuple[int, float, float, float, float]]:
    boxes = []
    for det in record.get("detections", []):
        try:
            class_id = int(det["class_id"])
            conf = float(det["confidence"])
            box = (float(det["x1"]), float(det["y1"]), float(det["x2"]), float(det["y2"]))
        except (KeyError, TypeError, ValueError):
            continue
        if class_id not in (0, 1) or conf < min_conf:
            continue
        boxes.append((class_id, *box))
    selected = record.get("selected")
    if isinstance(selected, dict):
        try:
            sid = int(selected["class_id"])
            sbox = (float(selected["x1"]), float(selected["y1"]), float(selected["x2"]), float(selected["y2"]))
            if sid in (0, 1) and not any(
                abs(b[1] - sbox[0]) < 1e-3 and abs(b[2] - sbox[1]) < 1e-3
                and abs(b[3] - sbox[2]) < 1e-3 and abs(b[4] - sbox[3]) < 1e-3
                for b in boxes
            ):
                boxes.append((sid, *sbox))
        except (KeyError, TypeError, ValueError):
            pass
    boxes.sort(key=lambda row: row[0])
    return boxes[:max_detections]


def _yolo(class_id: int, box: tuple[float, float, float, float], width: int, height: int) -> str:
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2.0 / width
    cy = (y1 + y2) / 2.0 / height
    bw = max(0.0, (x2 - x1) / width)
    bh = max(0.0, (y2 - y1) / height)
    return f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}"


def build(config_path: Path, output_dir: Path, frames_per_session: int, min_conf: float) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    config = _load_config(config_path)
    for split in ("train", "val", "test"):
        (output_dir / "images" / split).mkdir(parents=True)
        (output_dir / "labels" / split).mkdir(parents=True)
    manifest = []
    for entry in config["sessions"]:
        session_id = entry["session_id"]
        split = entry["split"]
        record_path = Path(entry["inference_dir"]) / "inference_frames.jsonl"
        video_path = Path(entry["capture_dir"]) / "capture.mp4"
        if not record_path.exists():
            raise FileNotFoundError(record_path)
        if not video_path.exists():
            raise FileNotFoundError(video_path)
        records = [
            json.loads(line)
            for line in record_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        records.sort(key=lambda row: int(row.get("frame_index", 0)))
        picks = _sample(records, frames_per_session)
        if not picks:
            raise ValueError(f"no frames selected for {session_id}")
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"cannot open video: {video_path}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        for record in picks:
            frame_index = int(record.get("frame_index", 0))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, image = cap.read()
            if not ok or image is None:
                raise RuntimeError(f"cannot read frame {frame_index}: {video_path}")
            stem = f"{session_id}_{frame_index:06d}"
            image_path = output_dir / "images" / split / f"{stem}.jpg"
            label_path = output_dir / "labels" / split / f"{stem}.txt"
            cv2.imwrite(str(image_path), image)
            labels = []
            for class_id, x1, y1, x2, y2 in _boxes(record, min_conf, max_detections=12):
                labels.append(_yolo(class_id, (x1, y1, x2, y2), width, height))
            label_path.write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")
            manifest.append({
                "split": split,
                "image": str(image_path.relative_to(output_dir)),
                "label": str(label_path.relative_to(output_dir)),
                "session_id": session_id,
                "agent_type": entry["agent_type"],
                "map": entry["map"],
                "frame_index": frame_index,
                "capture_time_s": record.get("capture_time_s"),
                "n_labels": len(labels),
            })
        cap.release()
    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0].keys()))
        writer.writeheader()
        writer.writerows(manifest)
    names = config.get("classes", ["enemy_head", "enemy_body"])
    (output_dir / "data.yaml").write_text(
        "path: .\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n"
        + "\n".join(f"  {i}: {name}" for i, name in enumerate(names))
        + "\n",
        encoding="utf-8",
    )
    meta = {
        "schema_version": "anticheat.pov_detection_dataset.v1",
        "source_config": str(config_path),
        "frames_per_session": frames_per_session,
        "min_conf": min_conf,
        "total_images": len(manifest),
        "prelabels": True,
        "review_required": True,
        "note": "Labels are old-model prelabels; manually review before training.",
    }
    (output_dir / "DATASET_META.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare POV detection prelabel dataset")
    parser.add_argument("--config", type=Path, default=Path("configs/pov_detection_sessions.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/pov_detection_v1"))
    parser.add_argument("--frames-per-session", type=int, default=20)
    parser.add_argument("--min-conf", type=float, default=0.35)
    args = parser.parse_args(argv)
    try:
        meta = build(args.config, args.output_dir, args.frames_per_session, args.min_conf)
    except Exception as exc:
        print(f"[ERROR] POV dataset preparation failed: {exc}", file=sys.stderr)
        return 2
    print(f"[INFO] POV dataset: {args.output_dir} ({meta['total_images']} images, prelabels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())