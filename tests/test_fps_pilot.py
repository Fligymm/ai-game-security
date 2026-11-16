from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from tools.capture_fps_pilot import (
    PROTOCOL_VERSION,
    build_metadata,
    validate_agent_type,
    validate_capture_source,
    validate_view_mode,
)
from tools.check_fps_pilot import check_pilot
from tools.run_cv_agent_offline import build_inference_meta
from vision.stream.session_recorder import SessionRecorder
from vision.stream.window_capture import WindowInfo, _cs2_window, validate_window_state


def _window(**overrides) -> WindowInfo:
    values = dict(
        hwnd=123,
        title="Counter-Strike 2",
        class_name="SDL_app",
        client_left=100,
        client_top=100,
        width=64,
        height=64,
        is_visible=True,
        is_minimized=False,
        is_foreground=True,
    )
    values.update(overrides)
    return WindowInfo(**values)


def _metadata(agent_type: str = "human"):
    source = "player_pov" if agent_type == "human" else "observer_followed_bot"
    return build_metadata(
        session_id="p0b_test",
        agent_type=agent_type,
        capture_source=source,
        view_mode="first_person",
        width=64,
        height=64,
        target_fps=10,
        roi=(100, 100, 164, 164),
        backend="test",
        scene="static_target",
        map_name="aim_botz",
        weapon="ak47",
        sensitivity=0.8,
        fov=90,
        operator_id="anonymous",
        notes="test",
        window=_window(),
        pov_attested=True,
        experiment_attested=True,
    )


def _make_valid_session(tmp_path: Path) -> Path:
    metadata = _metadata("human")
    recorder = SessionRecorder(tmp_path, metadata, video_fps=10)
    recorder.start()
    try:
        for frame_id in range(2):
            recorder.record_frame(
                np.zeros((64, 64, 3), dtype=np.uint8),
                timestamp_ns=frame_id * 100_000_000,
                frame_id=frame_id,
                detections=(),
                selected=None,
                applied_mouse=False,
                extra={"pilot": True},
            )
    finally:
        recorder.close()
    session_dir = tmp_path / metadata.session_id
    lifecycle_path = session_dir / "lifecycle.jsonl"
    events = [
        {"event": "session_created", "monotonic_ns": 1},
        {"event": "game_window_verified", "monotonic_ns": 2},
        {"event": "capture_started", "monotonic_ns": 3},
        {"event": "experiment_started", "monotonic_ns": 4},
        {"event": "experiment_finished", "monotonic_ns": 5},
        {"event": "capture_stopped", "monotonic_ns": 6},
        {"event": "manifest_generated", "monotonic_ns": 7},
        {
            "event": "video_artifact",
            "monotonic_ns": 8,
            "sha256": __import__("hashlib").sha256((session_dir / "capture.mp4").read_bytes()).hexdigest(),
        },
        {"event": "integrity_verified", "monotonic_ns": 9, "ok": True},
    ]
    lifecycle_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    return session_dir


def test_pilot_metadata_contains_pov_protocol_fields() -> None:
    meta = _metadata("human")
    assert meta.source == "p0b_human"
    assert meta.extra["protocol_version"] == PROTOCOL_VERSION
    assert meta.extra["agent_type"] == "human"
    assert meta.extra["view_mode"] == "first_person"
    assert meta.extra["capture_source"] == "player_pov"
    assert meta.extra["is_proxy"] is False
    assert meta.extra["real_control"] is False
    assert meta.extra["capture_mode"] == "screen_only"
    assert meta.extra["pov_attested"] is True
    assert meta.extra["experiment_attested"] is True


def test_third_person_and_free_view_are_rejected() -> None:
    with pytest.raises(ValueError, match="first_person"):
        validate_view_mode("third_person")
    with pytest.raises(ValueError, match="first_person"):
        validate_view_mode("free")


def test_capture_source_must_match_agent_type() -> None:
    assert validate_capture_source("human", "player_pov") == "player_pov"
    assert validate_capture_source("game_bot", "observer_followed_bot") == "observer_followed_bot"
    with pytest.raises(ValueError, match="requires capture_source"):
        validate_capture_source("human", "observer_followed_bot")


def test_cv_agent_and_real_cheat_are_not_capture_agents() -> None:
    with pytest.raises(ValueError):
        validate_agent_type("cv_agent")
    with pytest.raises(ValueError):
        validate_agent_type("real_cheat")


def test_window_state_validation_rejects_minimized_or_unfocused() -> None:
    assert validate_window_state(_window()) == []
    assert validate_window_state(_window(is_minimized=True))
    assert validate_window_state(_window(is_foreground=False))
    assert validate_window_state(_window(is_visible=False))


def test_cs2_window_detection_uses_process_not_localized_title() -> None:
    assert _cs2_window(_window(title="反恐精英：全球攻势", process_name="cs2.exe")) is True
    assert _cs2_window(_window(title="Counter-Strike 2", process_name="")) is True
    assert _cs2_window(_window(title="Steam", process_name="steam.exe")) is False


def test_valid_pilot_session_passes_with_hashes(tmp_path) -> None:
    session_dir = _make_valid_session(tmp_path)
    result = check_pilot(session_dir, verify_hash=True)
    assert result["ok"] is True, result
    assert result["statuses"]["FILE_INTEGRITY_VERIFIED"] is True
    assert result["statuses"]["VIDEO_DECODE_VERIFIED"] is True
    assert result["statuses"]["GAME_WINDOW_OBSERVED"] is True
    assert result["statuses"]["POV_MANUALLY_ATTESTED"] is True
    assert result["statuses"]["EXPERIMENT_MANUALLY_ATTESTED"] is True


def test_pilot_session_without_attestation_fails(tmp_path) -> None:
    session_dir = _make_valid_session(tmp_path)
    session_path = session_dir / "session.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    session["extra"]["pov_attested"] = False
    session_path.write_text(json.dumps(session), encoding="utf-8")
    result = check_pilot(session_dir, verify_hash=True)
    assert result["ok"] is False
    assert result["statuses"]["POV_MANUALLY_ATTESTED"] is False


def test_corrupted_video_fails_decode(tmp_path) -> None:
    session_dir = _make_valid_session(tmp_path)
    (session_dir / "capture.mp4").write_bytes(b"not a video")
    result = check_pilot(session_dir, verify_hash=False)
    assert result["ok"] is False
    assert result["statuses"]["VIDEO_DECODE_VERIFIED"] is False


def test_offline_inference_meta_records_source_association(tmp_path) -> None:
    video = tmp_path / "capture.mp4"
    video.write_bytes(b"video-bytes")
    session = {"session_id": "src1", "extra": {"agent_type": "human", "capture_source": "player_pov", "view_mode": "first_person"}}
    meta = build_inference_meta(
        source_session_dir=tmp_path,
        source_session=session,
        source_video=video,
        source_video_sha256="a" * 64,
        model_path=tmp_path / "best.onnx",
        model_sha256="b" * 64,
        config={"dry_run": True},
        output_files=[tmp_path / "inference.jsonl"],
    )
    assert meta["source_session_id"] == "src1"
    assert meta["source_video_sha256"] == "a" * 64
    assert meta["dry_run"] is True
    assert meta["real_control"] is False
    assert meta["apply_mouse"] is False