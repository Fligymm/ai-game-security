from __future__ import annotations

import csv

import numpy as np

from tools.analyze_false_negatives import _crop_with_margin
from tools.summarize_hard_examples import summarize


def test_crop_with_margin_stays_inside_image() -> None:
    image = np.zeros((100, 120, 3), dtype=np.uint8)
    crop = _crop_with_margin(image, [2, 3, 20, 30], margin_ratio=0.5)
    assert crop.shape[0] > 27
    assert crop.shape[1] > 18
    assert crop.shape[0] <= 100
    assert crop.shape[1] <= 120


def test_summarize_requires_all_rows(tmp_path) -> None:
    path = tmp_path / "review.csv"
    rows = [
        {
            "index": 0,
            "crop": "a.jpg",
            "contact_sheet": "s.jpg",
            "scene": "static_target",
            "session_id": "s",
            "frame_id": 1,
            "class_id": 0,
            "class_name": "enemy_head",
            "failure_type": "small",
            "notes": "",
        },
        {
            "index": 1,
            "crop": "b.jpg",
            "contact_sheet": "s.jpg",
            "scene": "slow_strafe",
            "session_id": "s",
            "frame_id": 2,
            "class_id": 0,
            "class_name": "enemy_head",
            "failure_type": "",
            "notes": "",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = summarize(path)

    assert report["ok"] is False
    assert report["total"] == 2
    assert report["reviewed"] == 1
    assert report["missing"] == ["b.jpg"]
    assert report["counts"] == {"small": 1}


def test_summarize_accepts_clear_miss_and_gbk(tmp_path) -> None:
    path = tmp_path / "review.csv"
    path.write_bytes(
        (
            "index,crop,contact_sheet,scene,session_id,frame_id,class_id,class_name,failure_type,notes\n"
            "0,a.jpg,s.jpg,static_target,s,1,0,enemy_head,clear_miss,目标清楚但没框\n"
        ).encode("gb18030")
    )

    report = summarize(path)

    assert report["ok"] is True
    assert report["total"] == 1
    assert report["counts"] == {"clear_miss": 1}