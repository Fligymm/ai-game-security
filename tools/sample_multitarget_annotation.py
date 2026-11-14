"""Sample a multi-target annotation set from new pilot captures.

Unlike ``sample_annotation.py``, this sampler reserves slots for frames where
the model already sees at least two heads.  That is only a hint: annotation
must count every visible head/body, including targets the model missed.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

try:
    from tools.sample_annotation import (
        SCENE_ORDER,
        _read_events,
        _read_json,
        choose_even,
        select_sessions,
    )
except ImportError:  # running as ``python tools/sample_multitarget_annotation.py``
    from sample_annotation import (  # type: ignore[no-redef]
        SCENE_ORDER,
        _read_events,
        _read_json,
        choose_even,
        select_sessions,
    )


def head_count(event: dict[str, Any]) -> int:
    return sum(1 for box in event.get("detections", []) if int(box.get("class_id", -1)) == 0)


def split_events(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "multi": [],
        "single": [],
        "empty": [],
        "other": [],
    }
    for event in events:
        heads = head_count(event)
        if heads >= 2:
            buckets["multi"].append(event)
        elif heads == 1:
            buckets["single"].append(event)
        elif not event.get("detections"):
            buckets["empty"].append(event)
        else:
            buckets["other"].append(event)
    return buckets


def _pick(
    buckets: dict[str, list[dict[str, Any]]],
    *,
    rng_seed: int,
    multi: int,
    single: int,
    empty: int,
    total: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    import random

    rng = random.Random(rng_seed)
    picked: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    used_ids: set[int] = set()

    def take(name: str, count: int) -> None:
        candidates = [
            event
            for event in buckets[name]
            if id(event) not in used_ids
        ]
        chosen = choose_even(candidates, min(count, len(candidates)), rng)
        for event in chosen:
            used_ids.add(id(event))
        picked.extend(chosen)
        counts[name] = len(chosen)

    take("multi", multi)
    take("single", single)
    take("empty", empty)

    # Fill shortfalls from any remaining event, but keep the reserved buckets
    # first so the set remains multi-target-heavy.
    remaining = [
        event
        for name in ("multi", "single", "other", "empty")
        for event in buckets[name]
        if id(event) not in used_ids
    ]
    need = total - len(picked)
    if need > 0:
        extra = choose_even(remaining, min(need, len(remaining)), rng)
        picked.extend(extra)
        counts["filled"] = len(extra)
    return picked, counts


def _extract(
    session_dir: Path,
    session: dict[str, Any],
    events: list[dict[str, Any]],
    output_dir: Path,
) -> list[dict[str, Any]]:
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
        for event in events:
            record_index = int(event["record_index"])
            cap.set(cv2.CAP_PROP_POS_FRAMES, record_index)
            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError(
                    f"cannot read {video_path} record_index={record_index}"
                )
            frame_id = int(event["frame_id"])
            stem = f"{session['scene']}__{session['session_id']}__f{frame_id:06d}"
            image_path = images_dir / f"{stem}.jpg"
            label_path = labels_dir / f"{stem}.txt"
            if not cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                raise RuntimeError(f"failed to write {image_path}")
            label_path.write_text("", encoding="utf-8")
            heads = head_count(event)
            items.append(
                {
                    "image": str(image_path.relative_to(output_dir)).replace("\\", "/"),
                    "label": str(label_path.relative_to(output_dir)).replace("\\", "/"),
                    "scene": session["scene"],
                    "session_id": session["session_id"],
                    "frame_id": frame_id,
                    "record_index": record_index,
                    "timestamp_ns": int(event["timestamp_ns"]),
                    "model_head_count": heads,
                    "model_is_multi": heads >= 2,
                    "model_selected": bool(event.get("selected")),
                    "model_detections": event.get("detections", []),
                    "label_status": "unlabeled",
                    "split": "unassigned",
                }
            )
    finally:
        cap.release()
    return items


def build_sample(
    pilot_root: Path,
    output_dir: Path,
    *,
    scenes: tuple[str, ...] = SCENE_ORDER,
    per_scene: int = 50,
    multi_per_scene: int = 20,
    single_per_scene: int = 20,
    empty_per_scene: int = 10,
    seed: int = 42,
) -> dict[str, Any]:
    if min(per_scene, multi_per_scene, single_per_scene, empty_per_scene) < 0:
        raise ValueError("sample counts must be non-negative")
    if multi_per_scene + single_per_scene + empty_per_scene > per_scene:
        raise ValueError("multi + single + empty must not exceed per-scene")
    if output_dir.exists():
        raise FileExistsError(f"output already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    sessions = select_sessions(pilot_root, scenes)
    if not sessions:
        raise RuntimeError(f"no matching sessions under {pilot_root}")
    all_items: list[dict[str, Any]] = []
    per_session: list[dict[str, Any]] = []
    for index, session_dir in enumerate(sessions):
        session = _read_json(session_dir / "session.json")
        events = _read_events(session_dir / "events.jsonl")
        buckets = split_events(events)
        chosen, picked_counts = _pick(
            buckets,
            rng_seed=seed + index * 1000,
            multi=multi_per_scene,
            single=single_per_scene,
            empty=empty_per_scene,
            total=per_scene,
        )
        if len(chosen) < per_scene:
            raise RuntimeError(
                f"{session['scene']}: only {len(chosen)} frames available, "
                f"need {per_scene}"
            )
        items = _extract(session_dir, session, chosen, output_dir)
        all_items.extend(items)
        per_session.append(
            {
                "scene": session["scene"],
                "session_id": session["session_id"],
                "session_dir": str(session_dir),
                "picked": picked_counts,
                "model_multi_available": len(buckets["multi"]),
                "model_single_available": len(buckets["single"]),
                "model_empty_available": len(buckets["empty"]),
            }
        )

    multi_frames = sum(1 for item in all_items if item["model_is_multi"])
    empty_frames = sum(1 for item in all_items if not item["model_detections"])
    manifest = {
        "schema_version": "multimodal.annotation_sample.v1_multitarget",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pilot_root": str(pilot_root),
        "per_scene": per_scene,
        "requested": {
            "multi_per_scene": multi_per_scene,
            "single_per_scene": single_per_scene,
            "empty_per_scene": empty_per_scene,
        },
        "seed": seed,
        "scenes": list(scenes),
        "sessions": [str(path) for path in sessions],
        "counts": {
            "frames": len(all_items),
            "model_multi_frames": multi_frames,
            "model_empty_frames": empty_frames,
        },
        "per_session": per_session,
        "items": all_items,
        "notes": [
            "model_head_count is a hint, not ground truth.",
            "Annotate every visible enemy_head/enemy_body, including targets the model missed.",
            "A frame with two visible heads must have two head boxes, even if the model only detected one.",
            "Keep the 90-frame pilot test out of this set.",
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(_readme(manifest), encoding="utf-8")
    (output_dir / "data.yaml").write_text(
        (
            "# Annotation-only data.yaml; split later by session.\n"
            f"path: {output_dir.resolve().as_posix()}\n"
            "train: images\n"
            "val: images\n"
            "\n"
            "nc: 2\n"
            "names:\n"
            "  0: enemy_head\n"
            "  1: enemy_body\n"
        ),
        encoding="utf-8",
    )
    return manifest


def _readme(manifest: dict[str, Any]) -> str:
    counts = manifest["counts"]
    return rf"""# 多目标标注样本

- 总帧数：{counts['frames']}
- 模型看到 ≥2 个 head 的帧：{counts['model_multi_frames']}
- 模型完全没检测的帧：{counts['model_empty_frames']}
- 场景：{', '.join(manifest['scenes'])}

## 规则

- `enemy_head` = 0，`enemy_body` = 1；
- 每张图标注所有可见的 head/body，包括模型没选中的目标；
- 一帧有 2 个可见 head，就必须有 2 个 head 框；
- 不要标 HUD/准星/队友；
- 空图保留空 `.txt`，不要删；
- 这张表里的 `model_detections` 只是参考，不是 ground truth。

## 标注完成后

```powershell
.\.venv\\Scripts\\python.exe tools\\check_multitarget_annotation.py `
  --annotation "runs\\pilot_20261115_multitarget\\annotation_multitarget"
```
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample multi-target frames for annotation")
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenes", nargs="+", default=list(SCENE_ORDER))
    parser.add_argument("--per-scene", type=int, default=50)
    parser.add_argument("--multi-per-scene", type=int, default=20)
    parser.add_argument("--single-per-scene", type=int, default=20)
    parser.add_argument("--empty-per-scene", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    summary = build_sample(
        args.pilot_root,
        args.output,
        scenes=tuple(args.scenes),
        per_scene=args.per_scene,
        multi_per_scene=args.multi_per_scene,
        single_per_scene=args.single_per_scene,
        empty_per_scene=args.empty_per_scene,
        seed=args.seed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()