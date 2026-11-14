from __future__ import annotations

import json

from tools.labelstudio_to_yolo import convert


def test_convert_writes_normalized_yolo(tmp_path) -> None:
    images = tmp_path / "images"
    labels = tmp_path / "labels"
    images.mkdir()
    (images / "a.jpg").write_bytes(b"not-a-real-jpeg")
    export = tmp_path / "export.json"
    export.write_text(
        json.dumps(
            [
                {
                    "file_upload": "a.jpg",
                    "annotations": [
                        {
                            "result": [
                                {
                                    "type": "rectanglelabels",
                                    "value": {
                                        "x": 10,
                                        "y": 20,
                                        "width": 30,
                                        "height": 40,
                                        "rectanglelabels": ["enemy_head"],
                                    },
                                }
                            ]
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    report = convert(export, images, labels)

    assert report["ok"] is True
    assert report["boxes"] == 1
    assert (labels / "a.txt").read_text(encoding="utf-8").strip() == (
        "0 0.250000 0.400000 0.300000 0.400000"
    )


def test_convert_matches_label_studio_prefixed_upload_name(tmp_path) -> None:
    images = tmp_path / "images"
    labels = tmp_path / "labels"
    images.mkdir()
    (images / "a.jpg").write_bytes(b"")
    export = tmp_path / "export.json"
    export.write_text(
        json.dumps(
            [
                {
                    "file_upload": "75a8c6d2-a.jpg",
                    "annotations": [
                        {
                            "result": [
                                {
                                    "type": "rectanglelabels",
                                    "value": {
                                        "x": 10,
                                        "y": 20,
                                        "width": 30,
                                        "height": 40,
                                        "rectanglelabels": ["enemy_body"],
                                    },
                                }
                            ]
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    report = convert(export, images, labels)

    assert report["ok"] is True
    assert report["boxes"] == 1
    assert (labels / "a.txt").read_text(encoding="utf-8").strip() == (
        "1 0.250000 0.400000 0.300000 0.400000"
    )


def test_convert_reports_missing_task(tmp_path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "a.jpg").write_bytes(b"")
    (images / "b.jpg").write_bytes(b"")
    export = tmp_path / "export.json"
    export.write_text("[]", encoding="utf-8")

    report = convert(export, images, tmp_path / "labels")

    assert report["ok"] is False
    assert report["missing"] == ["a.jpg", "b.jpg"]
    assert any("no Label Studio task" in error for error in report["errors"])