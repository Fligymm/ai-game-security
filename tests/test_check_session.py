from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tools.check_session import check_session
from tools.replay_session import render_session
from vision.stream.session_recorder import CaptureMetadata, SessionRecorder


def _make_session(tmp_path) -> Path:
    metadata = CaptureMetadata(
        session_id="checked_session",
        source="unit_test",
        game="unit_test",
        scene="synthetic",
        operator_id="pytest",
        width=32,
        height=24,
    )
    recorder = SessionRecorder(tmp_path / "captures", metadata, mode="frames", video_fps=1000)
    recorder.start()
    recorder.record_frame(
        np.zeros((24, 32, 3), dtype=np.uint8),
        timestamp_ns=0,
        frame_id=0,
        detections=[
            {"x1": 1, "y1": 2, "x2": 12, "y2": 14, "confidence": 0.9, "class_id": 0}
        ],
        selected={
            "x1": 1,
            "y1": 2,
            "x2": 12,
            "y2": 14,
            "confidence": 0.9,
            "class_id": 0,
            "class_name": "enemy_head",
            "track_id": 3,
            "delta_x": 5.0,
            "delta_y": -2.0,
        },
        mouse_delta=(2.0, -1.0),
    )
    recorder.record_frame(np.zeros((24, 32, 3), dtype=np.uint8), timestamp_ns=2_000_000, frame_id=1)
    recorder.close()
    return recorder.session_dir


def test_check_session_accepts_complete_capture(tmp_path) -> None:
    session_dir = _make_session(tmp_path)
    report = check_session(session_dir, verify_hash=True)
    assert report["ok"] is True, report
    assert report["stats"]["frames_recorded"] == 2
    assert report["stats"]["events"] == 2


def test_render_session_writes_overlay_video(tmp_path) -> None:
    session_dir = _make_session(tmp_path)
    output = render_session(session_dir, tmp_path / "replay.mp4", limit=2)
    assert output.exists()
    assert output.stat().st_size > 0


def test_check_session_detects_frame_count_mismatch(tmp_path) -> None:
    session_dir = _make_session(tmp_path)
    session_path = session_dir / "session.json"
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    payload["frames_recorded"] = 99
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    report = check_session(session_dir)
    assert report["ok"] is False
    assert any("events count" in error for error in report["errors"])