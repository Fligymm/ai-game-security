"""Build a small, stratified frame sample for manual detection labeling.

The pilot captures are unlabeled control sessions.  This tool extracts a
balanced set of frames with and without a model-selected target so the next
step can measure detection recall as well as false positives.  Model boxes in
the manifest are references only; they are not ground truth.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2


SCENE_ORDER = ("static_target", "slow_strafe", "fast_strafe")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                events.append(json.loads(line))
    return events


def choose_even(items: list[dict[str, Any]], count: int, rng: random.Random) -> list[dict[str, Any]]:
    """Pick ``count`` items spread across the timeline."""

    if count <= 0 or not items:
        return []
    if count >= len(items):
        return list(items)
    picked: list[dict[str, Any]] = []
    for index in range(count):
        start = index * len(items) // count
        end = (index + 1) * len(items) // count
        picked.append(items[rng.randrange(start, end)])
    return picked


def select_sessions(pilot_root: Path, scenes: Iterable[str]) -> list[Path]:
    wanted = set(scenes)
    by_scene: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    for session_dir in (pilot_root / "captures").iterdir():
        session_path = session_dir / "session.json"
        if not session_path.is_file():
            continue
        session = _read_json(session_path)
        scene = session.get("scene")
        if scene not in wanted:
            continue
        by_scene[scene].append((int(session.get("started_at_wall_ns", 0)), session_dir))

    selected: list[Path] = []
    for scene in scenes:
        candidates = sorted(by_scene.get(scene, []), key=lambda item: item[0])
        if candidates:
            selected.append(candidates[-1][1])
    return selected


def _split_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    positive = [event for event in events if event.get("selected")]
    negative = [event for event in events if not event.get("selected")]
    return positive, negative


def sample_session(
    session_dir: Path,
    output_dir: Path,
    *,
    per_scene: int,
    positive_ratio: float,
    seed: int,
) -> list[dict[str, Any]]:
    session = _read_json(session_dir / "session.json")
    events = _read_events(session_dir / "events.jsonl")
    positive, negative = _split_events(events)
    if not positive and not negative:
        raise RuntimeError(f"no events in {session_dir}")

    positive_count = min(len(positive), max(1, round(per_scene * positive_ratio)))
    negative_count = min(len(negative), per_scene - positive_count)
    # If one side is short, fill the remainder from the other side.
    if positive_count + negative_count < per_scene:
        extra_positive = min(len(positive) - positive_count, per_scene - positive_count - negative_count)
        positive_count += max(0, extra_positive)
    if positive_count + negative_count < per_scene:
        extra_negative = min(len(negative) - negative_count, per_scene - positive_count - negative_count)
        negative_count += max(0, extra_negative)

    rng = random.Random(seed + sum(ord(ch) for ch in session["scene"]))
    chosen = choose_even(positive, positive_count, rng) + choose_even(negative, negative_count, rng)

    video_path = session_dir / str(session.get("video_path") or "capture.mp4")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {video_path}")

    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    try:
        for event in chosen:
            record_index = int(event["record_index"])
            cap.set(cv2.CAP_PROP_POS_FRAMES, record_index)
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError(
                    f"cannot read {video_path} frame record_index={record_index}"
                )
            frame_id = int(event["frame_id"])
            stem = f"{session['scene']}__{session['session_id']}__f{frame_id:06d}"
            image_path = images_dir / f"{stem}.jpg"
            label_path = labels_dir / f"{stem}.txt"
            if not cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                raise RuntimeError(f"failed to write {image_path}")
            label_path.write_text("", encoding="utf-8")
            items.append(
                {
                    "image": str(image_path.relative_to(output_dir)).replace("\\", "/"),
                    "label": str((labels_dir / f"{stem}.txt").relative_to(output_dir)).replace("\\", "/"),
                    "scene": session["scene"],
                    "session_id": session["session_id"],
                    "frame_id": frame_id,
                    "record_index": record_index,
                    "timestamp_ns": int(event["timestamp_ns"]),
                    "model_selected": bool(event.get("selected")),
                    "model_detections": event.get("detections", []),
                    "label_status": "unlabeled",
                    "split": "pilot_eval",
                }
            )
    finally:
        cap.release()
    return items


def build_sample(
    pilot_root: Path,
    output_dir: Path,
    *,
    scenes: Iterable[str] = SCENE_ORDER,
    per_scene: int = 30,
    positive_ratio: float = 0.67,
    seed: int = 42,
) -> dict[str, Any]:
    if per_scene <= 0:
        raise ValueError("per_scene must be positive")
    if not 0.0 <= positive_ratio <= 1.0:
        raise ValueError("positive_ratio must be in [0, 1]")
    scene_list = list(scenes)
    sessions = select_sessions(pilot_root, scene_list)
    if not sessions:
        raise RuntimeError(f"no matching sessions under {pilot_root}")

    output_dir.mkdir(parents=True, exist_ok=False)
    items: list[dict[str, Any]] = []
    for index, session_dir in enumerate(sessions):
        items.extend(
            sample_session(
                session_dir,
                output_dir,
                per_scene=per_scene,
                positive_ratio=positive_ratio,
                seed=seed + index * 1000,
            )
        )

    manifest = {
        "schema_version": "multimodal.annotation_sample.v0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pilot_root": str(pilot_root),
        "per_scene": per_scene,
        "positive_ratio": positive_ratio,
        "seed": seed,
        "scenes": scene_list,
        "sessions": [str(path) for path in sessions],
        "counts": {
            "frames": len(items),
            "with_model_selected": sum(1 for item in items if item["model_selected"]),
            "without_model_selected": sum(1 for item in items if not item["model_selected"]),
        },
        "items": items,
        "notes": [
            "Images are sampled frames from pilot control sessions.",
            "model_detections are model outputs, not ground truth.",
            "Label every visible enemy_head and enemy_body, including unselected targets.",
            "Use one YOLO label file per image; empty file means no target.",
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(_readme(manifest), encoding="utf-8")
    return manifest


def _readme(manifest: dict[str, Any]) -> str:
    counts = manifest["counts"]
    return f"""# Pilot annotation sample

- frames: {counts['frames']}
- with model-selected target: {counts['with_model_selected']}
- without model-selected target: {counts['without_model_selected']}
- scenes: {', '.join(manifest['scenes'])}

## Label rules

- `enemy_head` -> class id `0`
- `enemy_body` -> class id `1`
- Draw a tight box around every visible target, including targets the model did
  not select.
- If a target is heavily occluded, skip it only when its extent is not
  inferable; do not label the crosshair or HUD.
- Empty images are valid; leave an empty `.txt` file.

## Output

- `images/`: JPEG frames
- `labels/`: YOLO `.txt` labels, one row per box:
  `<class_id> <x_center> <y_center> <width> <height>` normalized to 0–1
- `manifest.json`: source frame, scene, timestamp, and model detections

`model_detections` in the manifest are references only. Do not copy them as
ground truth.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample pilot frames for manual detection labeling")
    parser.add_argument("--pilot", type=Path, required=True, help="Pilot root containing captures/")
    parser.add_argument("--output", type=Path, required=True, help="New annotation directory")
    parser.add_argument("--per-scene", type=int, default=30, help="Frames per scene")
    parser.add_argument("--positive-ratio", type=float, default=0.67, help="Fraction sampled with model-selected target")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scene", action="append", choices=SCENE_ORDER, help="Limit to one or more scenes")
    args = parser.parse_args()

    manifest = build_sample(
        args.pilot,
        args.output,
        scenes=args.scene or SCENE_ORDER,
        per_scene=args.per_scene,
        positive_ratio=args.positive_ratio,
        seed=args.seed,
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()