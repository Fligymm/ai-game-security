from __future__ import annotations

import csv
import json
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from cv_agent.control import AimController, BaseMouseBackend, CSVLoggerBackend, Win32APIBackend
from cv_agent.orchestrator import AimPipeline
from vision.detection.detection import Detection
from vision.stream.realtime_loop import RealtimeAimLoop, RealtimeLoopConfig
from vision.stream.safety import VK_ESCAPE, VK_F12, GlobalHotkeyKillSwitch


class FakeDetector:
    class_names = {0: "enemy_head", 1: "enemy_body"}

    def detect_frame(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        return [
            Detection(
                width / 2 + 80,
                height / 2 - 40,
                width / 2 + 100,
                height / 2 - 20,
                0.9,
                0,
            )
        ]


class FakeGrabber:
    roi_width = 640
    roi_height = 640

    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def get_latest_frame(self) -> np.ndarray:
        return np.zeros((640, 640, 3), dtype=np.uint8)


class RecordingBackend(BaseMouseBackend):
    supports_real_output = True

    def __init__(self) -> None:
        self.moves: list[tuple[int, int]] = []

    def send_relative_move(self, dx: int, dy: int) -> None:
        self.moves.append((int(dx), int(dy)))

    def reset(self) -> None:
        self.moves.clear()


def _ready_kill_switch() -> SimpleNamespace:
    return SimpleNamespace(
        available=True,
        is_running=True,
        paused=False,
        stopped=False,
        start=lambda: None,
        stop=lambda: None,
    )


def _loop(
    backend: BaseMouseBackend,
    *,
    apply_mouse: bool,
    record_dir=None,
) -> RealtimeAimLoop:
    pipeline = AimPipeline(
        detector=FakeDetector(),
        backend=backend,
        output_confirm_frames=1,
    )
    loop = RealtimeAimLoop(
        grabber=FakeGrabber(),
        pipeline=pipeline,
        config=RealtimeLoopConfig(
            apply_mouse=apply_mouse,
            hotkeys_enabled=False,
            debug_overlay=False,
            record_dir=str(record_dir) if record_dir is not None else None,
            record_fps=1_000_000,
            record_mode="frames",
            record_source="unit_test",
        ),
    )
    # The test does not exercise ByteTrack; keep the pipeline deterministic.
    loop.tracker = None
    loop.pipeline.tracker = None
    if apply_mouse:
        loop.kill_switch = _ready_kill_switch()
    return loop


def _frame() -> np.ndarray:
    return np.zeros((640, 640, 3), dtype=np.uint8)


def test_default_config_is_dry_run() -> None:
    assert RealtimeLoopConfig().apply_mouse is False


def test_csv_backend_is_not_real_output(tmp_path) -> None:
    backend = CSVLoggerBackend(tmp_path / "unused.csv")
    try:
        assert backend.supports_real_output is False
        assert AimController(backend).can_apply is False
    finally:
        backend.close()


def test_dry_run_logs_one_event_and_keeps_planned_trajectory(tmp_path) -> None:
    backend = CSVLoggerBackend(tmp_path / "dry.csv")
    loop = _loop(backend, apply_mouse=False)
    try:
        result = loop.step(_frame())
        assert result.trajectory is not None
        assert len(result.trajectory.points) > 1
        assert result.applied_mouse is False
    finally:
        loop.pipeline.controller.close()

    rows = list(csv.reader((tmp_path / "dry.csv").open(encoding="utf-8")))
    assert len(rows) == 2  # header + one correction event


def test_realtime_loop_records_multimodal_session(tmp_path) -> None:
    backend = CSVLoggerBackend(tmp_path / "recorded.csv")
    loop = _loop(backend, apply_mouse=False, record_dir=tmp_path / "captures")
    try:
        loop.step(_frame())
        loop.step(_frame())
        loop.stop()
    finally:
        loop.pipeline.controller.close()

    sessions = list((tmp_path / "captures").iterdir())
    assert len(sessions) == 1
    session = sessions[0]
    events = [
        json.loads(line)
        for line in (session / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["frame_id"] for event in events] == [0, 1]
    trajectory = events[0]["extra"]["trajectory"]
    assert trajectory is not None
    assert len(trajectory["points"]) >= 2
    assert len(list((session / "frames").glob("*.jpg"))) == 2
    manifest = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["frames_recorded"] == 2
    assert manifest["session"]["source"] == "unit_test"


def test_active_request_with_recording_only_backend_falls_back_to_csv(tmp_path) -> None:
    backend = CSVLoggerBackend(tmp_path / "fallback.csv")
    loop = _loop(backend, apply_mouse=True)
    try:
        result = loop.step(_frame())
        assert result.applied_mouse is False
    finally:
        loop.pipeline.controller.close()

    rows = list(csv.reader((tmp_path / "fallback.csv").open(encoding="utf-8")))
    assert len(rows) == 2


def test_active_request_with_real_capable_backend_reports_applied() -> None:
    backend = RecordingBackend()
    loop = _loop(backend, apply_mouse=True)
    try:
        result = loop.step(_frame())
        assert result.applied_mouse is True
        assert backend.moves
    finally:
        loop.pipeline.controller.close()


def test_enter_fails_closed_when_kill_switch_is_unavailable(tmp_path) -> None:
    loop = _loop(CSVLoggerBackend(tmp_path / "unused_enter.csv"), apply_mouse=True)
    loop.kill_switch = None
    try:
        with pytest.raises(RuntimeError, match="kill switch"):
            loop.__enter__()
        assert loop.grabber.stopped >= 1
    finally:
        loop.pipeline.controller.close()


def test_win32_dry_run_never_calls_handler() -> None:
    calls: list[tuple[int, int]] = []
    backend = Win32APIBackend(dry_run=True, custom_handler=lambda dx, dy: calls.append((dx, dy)))
    backend.send_relative_move(3, 4)
    assert calls == []
    assert backend.moves == [(3, 4)]
    assert backend.supports_real_output is False


def test_win32_real_mode_requires_handler() -> None:
    calls: list[tuple[int, int]] = []
    backend = Win32APIBackend(dry_run=False, custom_handler=lambda dx, dy: calls.append((dx, dy)))
    backend.send_relative_move(3, 4)
    assert calls == [(3, 4)]
    assert backend.supports_real_output is True

    with pytest.raises(RuntimeError, match="custom_handler"):
        Win32APIBackend(dry_run=False).send_relative_move(1, 1)


def test_polling_fallback_toggles_pause_and_stops() -> None:
    switch = GlobalHotkeyKillSwitch()
    keys = {VK_ESCAPE: False, VK_F12: False}
    switch._key_down = lambda vk: keys[vk]  # type: ignore[method-assign]

    thread = threading.Thread(target=switch._poll_loop, daemon=True)
    thread.start()
    assert switch._ready.wait(timeout=1.0)

    keys[VK_ESCAPE] = True
    time.sleep(0.05)
    assert switch.paused is True
    keys[VK_ESCAPE] = False
    time.sleep(0.05)

    keys[VK_F12] = True
    time.sleep(0.05)
    assert switch.stopped is True
    thread.join(timeout=1.0)
    assert not thread.is_alive()