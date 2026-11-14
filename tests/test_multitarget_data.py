from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from tools.check_multitarget_annotation import _validate_label, check
from tools.sample_multitarget_annotation import head_count, split_events


def _event(heads: int, bodies: int = 0) -> dict:
    detections = [{"class_id": 0} for _ in range(heads)]
    detections.extend({"class_id": 1} for _ in range(bodies))
    return {"detections": detections}


def test_split_events_by_model_head_count() -> None:
    events = [_event(2), _event(1), _event(0), _event(0, 1)]
    buckets = split_events(events)

    assert head_count(events[0]) == 2
    assert len(buckets["multi"]) == 1
    assert len(buckets["single"]) == 1
    assert len(buckets["empty"]) == 1
    assert len(buckets["other"]) == 1


def test_validate_label_rejects_bad_fields(tmp_path) -> None:
    path = tmp_path / "x.txt"
    path.write_text("0 0.5 0.5 0.2 0.2\n1 0.5 0.5\n0 1.2 0.5 0.2 0.2\n", encoding="utf-8")
    boxes, errors = _validate_label(path)

    assert len(boxes) == 1
    assert len(errors) == 2


def test_check_reports_multi_and_empty(tmp_path) -> None:
    root = tmp_path / "annotation"
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir()
    items = []
    for index, lines in enumerate(("0 0.5 0.5 0.1 0.1\n0 0.3 0.3 0.1 0.1\n", "")):
        image = root / "images" / f"{index}.jpg"
        cv2.imwrite(str(image), np.zeros((32, 32, 3), dtype=np.uint8))
        label = root / "labels" / f"{index}.txt"
        label.write_text(lines, encoding="utf-8")
        items.append(
            {
                "image": f"images/{index}.jpg",
                "label": f"labels/{index}.txt",
                "scene": "static_target",
                "session_id": "s",
            }
        )
    (root / "manifest.json").write_text(json.dumps({"items": items}), encoding="utf-8")

    report = check(root, min_frames=2, min_multi=1, min_empty=1)

    assert report["ok"] is True
    assert report["multi_target_frames"] == 1
    assert report["empty_frames"] == 1
    assert report["class_counts"] == {"enemy_head": 2}