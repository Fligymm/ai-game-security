from __future__ import annotations

import json

import numpy as np
import pytest

from vision.stream.session_recorder import CaptureMetadata, SessionRecorder


def _metadata(session_id: str = "unit_session", target_fps: int = 60) -> CaptureMetadata:
    return CaptureMetadata(
        session_id=session_id,
        source="unit_test",
        game="unit_test",
        scene="synthetic",
        operator_id="pytest",
        width=64,
        height=48,
        target_fps=target_fps,
    )


def _frame(value: int = 0) -> np.ndarray:
    return np.full((48, 64, 3), value, dtype=np.uint8)


def test_records_frames_events_session_and_manifest(tmp_path) -> None:
    recorder = SessionRecorder(tmp_path / "captures", _metadata(), mode="frames", video_fps=1000)
    recorder.start()
    assert recorder.record_frame(
        _frame(10),
        timestamp_ns=1_000_000,
        frame_id=0,
        detections=[{"x1": 1, "y1": 2, "x2": 3, "y2": 4, "confidence": 0.9, "class_id": 0}],
        selected={"track_id": 7, "class_name": "enemy_head"},
        applied_mouse=False,
        mouse_delta=(1.5, -2.0),
    )
    assert recorder.record_frame(
        _frame(20),
        timestamp_ns=2_000_000,
        frame_id=1,
        applied_mouse=True,
        mouse_delta=(3.0, 4.0),
    )
    recorder.close()

    session_dir = tmp_path / "captures" / "unit_session"
    assert (session_dir / "events.jsonl").exists()
    assert (session_dir / "session.json").exists()
    assert (session_dir / "manifest.json").exists()
    assert len(list((session_dir / "frames").glob("*.jpg"))) == 2

    events = [json.loads(line) for line in (session_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [event["frame_id"] for event in events] == [0, 1]
    assert events[0]["detections"][0]["class_id"] == 0
    assert events[0]["selected"]["track_id"] == 7
    assert events[1]["applied_mouse"] is True

    session = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))
    assert session["status"] == "closed"
    assert session["frames_recorded"] == 2
    assert session["frames_seen"] == 2

    manifest = json.loads((session_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["frames_recorded"] == 2
    assert manifest["quality"]["timestamp_monotonic"] is True
    assert any(item["path"] == "events.jsonl" for item in manifest["files"])


def test_sampling_skips_frames_before_interval(tmp_path) -> None:
    recorder = SessionRecorder(tmp_path / "captures", _metadata("sampled", target_fps=120), mode="frames", video_fps=60)
    recorder.start()
    assert recorder.record_frame(_frame(), timestamp_ns=0, frame_id=0)
    assert not recorder.record_frame(_frame(), timestamp_ns=10_000_000, frame_id=1)
    assert recorder.record_frame(_frame(), timestamp_ns=20_000_000, frame_id=2)
    recorder.close()

    session = json.loads(
        (tmp_path / "captures" / "sampled" / "session.json").read_text(encoding="utf-8")
    )
    assert session["frames_seen"] == 3
    assert session["frames_recorded"] == 2
    assert session["frames_skipped"] == 1


def test_equal_rate_does_not_drop_burst_frames(tmp_path) -> None:
    recorder = SessionRecorder(
        tmp_path / "captures",
        _metadata("equal_rate", target_fps=30),
        mode="frames",
        video_fps=1000,
    )
    recorder.start()
    for index in range(4):
        assert recorder.record_frame(_frame(index), timestamp_ns=index * 10_000_000, frame_id=index)
    recorder.close()

    session = json.loads(
        (tmp_path / "captures" / "equal_rate" / "session.json").read_text(encoding="utf-8")
    )
    assert session["frames_seen"] == 4
    assert session["frames_recorded"] == 4
    assert session["frames_skipped"] == 0
    assert session["video_fps"] == 30


def test_video_mode_writes_playable_container(tmp_path) -> None:
    recorder = SessionRecorder(tmp_path / "captures", _metadata("video_session"), mode="video", video_fps=30)
    recorder.start()
    recorder.record_frame(_frame(1), timestamp_ns=0, frame_id=0)
    recorder.record_frame(_frame(2), timestamp_ns=34_000_000, frame_id=1)
    recorder.close()

    video = tmp_path / "captures" / "video_session" / "capture.mp4"
    assert video.exists()
    assert video.stat().st_size > 0


def test_duplicate_session_directory_is_rejected(tmp_path) -> None:
    first = SessionRecorder(tmp_path / "captures", _metadata("duplicate"), mode="frames")
    first.start()
    try:
        with pytest.raises(FileExistsError):
            SessionRecorder(tmp_path / "captures", _metadata("duplicate"), mode="frames").start()
    finally:
        first.close()