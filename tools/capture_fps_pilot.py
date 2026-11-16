"""Fail-closed first-person FPS POV capture for P0-B.

This tool records a specific CS2 game window's client area. It never starts the
game, never starts a CV agent, and never sends mouse/keyboard input. If the game
window is missing, minimized, unfocused, or resized, capture aborts instead of
silently recording the desktop.

P0-B capture supports only:
  * human + player_pov
  * game_bot + observer_followed_bot

CV Agent runs are offline dry-run inference over already captured H/B videos
(see tools/run_cv_agent_offline.py), not live capture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.check_session import check_session
from vision.stream.session_recorder import CaptureMetadata, SessionRecorder
from vision.stream.window_capture import (
    GameWindowError,
    WindowCapture,
    WindowCaptureError,
    WindowInfo,
)


AGENT_TYPES = {
    "human": ("H", "player_capture"),
    "game_bot": ("B", "observer_capture"),
}
CAPTURE_SOURCES = {
    "human": "player_pov",
    "game_bot": "observer_followed_bot",
}
DEFAULT_OUTPUT = Path("runs/captures/p0b_pilot")
PROTOCOL_VERSION = "anticheat.p0b.v2"
VIEW_MODES = ("first_person", "third_person", "free")
CAPTURE_MODES = ("screen_only",)


class LifecycleError(RuntimeError):
    """Raised when lifecycle logging cannot be written safely."""


class LifecycleLogger:
    """Append-only JSONL lifecycle logger with wall and monotonic timestamps."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8", buffering=1)

    def write(self, event: str, **fields: object) -> None:
        if self._handle.closed:
            raise LifecycleError("lifecycle logger is closed")
        payload = {
            "event": event,
            "wall_time_ns": time.time_ns(),
            "wall_time_iso": datetime.now(timezone.utc).isoformat(),
            "monotonic_ns": time.perf_counter_ns(),
            **fields,
        }
        self._handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()


def _timestamp_session_id(agent_type: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"p0b_{agent_type}_{stamp}"


def validate_agent_type(value: str) -> str:
    if value not in AGENT_TYPES:
        raise ValueError(f"agent_type must be one of {sorted(AGENT_TYPES)}")
    return value


def validate_view_mode(value: str) -> str:
    if value not in VIEW_MODES:
        raise ValueError(f"view_mode must be one of {VIEW_MODES}")
    if value != "first_person":
        raise ValueError(
            "P0-B capture accepts first_person only; "
            "third_person/free view must not be marked as P0-B data"
        )
    return value


def validate_capture_source(agent_type: str, capture_source: str) -> str:
    if capture_source not in CAPTURE_SOURCES.values():
        raise ValueError(f"capture_source must be one of {sorted(set(CAPTURE_SOURCES.values()))}")
    expected = CAPTURE_SOURCES[validate_agent_type(agent_type)]
    if capture_source != expected:
        raise ValueError(
            f"agent_type={agent_type!r} requires capture_source={expected!r}; "
            f"got {capture_source!r}. Do not label third-person/free view as POV."
        )
    return capture_source


def _window_payload(window: WindowInfo | None) -> dict[str, object] | None:
    return asdict(window) if window is not None else None


def build_metadata(
    *,
    session_id: str,
    agent_type: str,
    capture_source: str,
    view_mode: str,
    width: int,
    height: int,
    target_fps: int,
    roi: tuple[int, int, int, int] | None,
    backend: str,
    scene: str,
    map_name: str,
    weapon: str,
    sensitivity: float,
    fov: int,
    operator_id: str,
    notes: str,
    window: WindowInfo | None,
    pov_attested: bool,
    experiment_attested: bool,
    capture_mode: str = "screen_only",
) -> CaptureMetadata:
    """Build protocol-complete metadata without inferring POV from agent_type."""

    agent_type = validate_agent_type(agent_type)
    view_mode = validate_view_mode(view_mode)
    capture_source = validate_capture_source(agent_type, capture_source)
    if capture_mode not in CAPTURE_MODES:
        raise ValueError(f"capture_mode must be one of {CAPTURE_MODES}")
    hint, label_source = AGENT_TYPES[agent_type]
    return CaptureMetadata(
        session_id=session_id,
        source=f"p0b_{agent_type}",
        game="cs2_offline",
        scene=scene,
        operator_id=operator_id,
        width=width,
        height=height,
        target_fps=target_fps,
        roi=roi,
        backend=backend,
        notes=notes,
        extra={
            "protocol_version": PROTOCOL_VERSION,
            "agent_type": agent_type,
            "agent_label": hint,
            "view_mode": view_mode,
            "capture_source": capture_source,
            "label_source": label_source,
            "label_confidence": "certain",
            "is_proxy": False,
            "real_control": False,
            "capture_mode": capture_mode,
            "map": map_name,
            "scene": scene,
            "weapon": weapon,
            "sensitivity": sensitivity,
            "fov": fov,
            "window": _window_payload(window),
            "pov_attested": bool(pov_attested),
            "experiment_attested": bool(experiment_attested),
        },
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record a fail-closed first-person offline FPS POV session",
    )
    parser.add_argument("--agent-type", required=True, choices=sorted(AGENT_TYPES))
    parser.add_argument(
        "--capture-source",
        required=True,
        choices=tuple(sorted(set(CAPTURE_SOURCES.values()))),
    )
    parser.add_argument("--view-mode", required=True, choices=VIEW_MODES)
    parser.add_argument("--scene", default="unspecified")
    parser.add_argument("--map-name", default="unspecified")
    parser.add_argument("--weapon", default="unspecified")
    parser.add_argument("--sensitivity", type=float, default=0.0)
    parser.add_argument("--fov", type=int, default=0)
    parser.add_argument("--operator-id", default="anonymous")
    parser.add_argument("--notes", default="")
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="target capture/video fps; 30 is the safe default for 1920x1080 mss capture",
    )
    parser.add_argument(
        "--window-title",
        default="",
        help="optional title substring override; default auto-detects cs2.exe",
    )
    parser.add_argument(
        "--focus-window",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="bring the CS2 window to the foreground before capture (default: true)",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--mode", choices=("video", "frames"), default="video")
    parser.add_argument(
        "--confirm-offline",
        action="store_true",
        help="required acknowledgement that this is an offline/closed environment",
    )
    parser.add_argument(
        "--attest-pov",
        action="store_true",
        help="manual attestation that the recorded view is the requested first-person POV",
    )
    parser.add_argument(
        "--attest-experiment",
        action="store_true",
        help="manual attestation that the experiment was run as described",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate arguments and print planned metadata without capturing",
    )
    return parser


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not args.confirm_offline:
        parser.error("--confirm-offline is required; no capture without it")
    if not args.attest_pov:
        parser.error("--attest-pov is required; POV cannot be inferred from agent_type")
    if not args.attest_experiment:
        parser.error("--attest-experiment is required; manual experiment attestation is not automatic")
    if args.duration <= 0 or args.duration > 600:
        parser.error("--duration must be in (0, 600] seconds")
    if args.fps <= 0 or args.fps > 240:
        parser.error("--fps must be in (0, 240]")
    if args.sensitivity < 0 or args.fov < 0:
        parser.error("sensitivity and FOV must be non-negative")
    try:
        validate_agent_type(args.agent_type)
        validate_view_mode(args.view_mode)
        validate_capture_source(args.agent_type, args.capture_source)
    except ValueError as exc:
        parser.error(str(exc))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(
    recorder: SessionRecorder,
    capture: WindowCapture,
    *,
    duration: float,
    fps: int,
    lifecycle: LifecycleLogger,
) -> tuple[int, float]:
    started = time.perf_counter()
    frame_id = 0
    target_interval = 1.0 / float(fps)
    while time.perf_counter() - started < duration:
        loop_started = time.perf_counter()
        frame = capture.get_frame()
        timestamp_ns = capture.last_frame_timestamp_ns or time.perf_counter_ns()
        recorder.record_frame(
            frame,
            timestamp_ns=timestamp_ns,
            frame_id=frame_id,
            detections=(),
            selected=None,
            applied_mouse=False,
            mouse_delta=None,
            extra={"pilot": True, "frame_index": frame_id},
        )
        frame_id += 1
        remaining = target_interval - (time.perf_counter() - loop_started)
        if remaining > 0:
            time.sleep(remaining)
    return frame_id, time.perf_counter() - started


def _capture(args: argparse.Namespace) -> Path:
    session_id = args.session_id or _timestamp_session_id(args.agent_type)
    session_dir = args.output_dir / session_id
    capture: WindowCapture | None = None
    recorder: SessionRecorder | None = None
    lifecycle: LifecycleLogger | None = None
    aborted = False
    try:
        capture = WindowCapture(
            title_contains=args.window_title or None,
            target_fps=args.fps,
            focus=args.focus_window,
        )
        capture.start()
        window = capture.window
        metadata = build_metadata(
            session_id=session_id,
            agent_type=args.agent_type,
            capture_source=args.capture_source,
            view_mode=args.view_mode,
            width=window.width,
            height=window.height,
            target_fps=args.fps,
            roi=(window.client_left, window.client_top, window.client_left + window.width, window.client_top + window.height),
            backend="mss-window",
            scene=args.scene,
            map_name=args.map_name,
            weapon=args.weapon,
            sensitivity=args.sensitivity,
            fov=args.fov,
            operator_id=args.operator_id,
            notes=args.notes,
            window=window,
            pov_attested=args.attest_pov,
            experiment_attested=args.attest_experiment,
        )
        recorder = SessionRecorder(
            args.output_dir,
            metadata,
            video_fps=args.fps,
            mode=args.mode,
        )
        recorder.start()
        lifecycle = LifecycleLogger(session_dir / "lifecycle.jsonl")
        lifecycle.write("session_created", session_id=session_id, session_dir=str(session_dir))
        lifecycle.write("game_window_verified", window=_window_payload(window))
        lifecycle.write("capture_started", backend="mss-window", target_fps=args.fps)
        lifecycle.write("experiment_started", view_mode=args.view_mode, capture_source=args.capture_source)
        frames, elapsed = _record(
            recorder,
            capture,
            duration=args.duration,
            fps=args.fps,
            lifecycle=lifecycle,
        )
        lifecycle.write("experiment_finished", frames=frames, requested_duration_s=args.duration)
        return session_dir
    except KeyboardInterrupt:
        aborted = True
        if lifecycle is not None:
            lifecycle.write("capture_aborted", reason="KeyboardInterrupt")
        raise
    except (GameWindowError, WindowCaptureError, Exception) as exc:
        aborted = True
        if lifecycle is not None:
            lifecycle.write("capture_aborted", reason=str(exc), error_type=type(exc).__name__)
        raise
    finally:
        if capture is not None:
            capture.stop()
        if recorder is not None:
            try:
                recorder.close()
            finally:
                pass
        if lifecycle is not None:
            lifecycle.write("capture_stopped", aborted=aborted)
            manifest_path = session_dir / "manifest.json"
            if manifest_path.is_file():
                lifecycle.write("manifest_generated", manifest_path=str(manifest_path))
                video_path = session_dir / "capture.mp4"
                if video_path.is_file():
                    lifecycle.write(
                        "video_artifact",
                        path=str(video_path),
                        size_bytes=video_path.stat().st_size,
                        sha256=_sha256(video_path),
                    )
                result = check_session(session_dir, verify_hash=True)
                lifecycle.write(
                    "integrity_verified",
                    ok=bool(result.get("ok")),
                    errors=result.get("errors", []),
                    warnings=result.get("warnings", []),
                )
            lifecycle.close()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_args(parser, args)

    if args.dry_run:
        session_id = args.session_id or _timestamp_session_id(args.agent_type)
        metadata = build_metadata(
            session_id=session_id,
            agent_type=args.agent_type,
            capture_source=args.capture_source,
            view_mode=args.view_mode,
            width=0,
            height=0,
            target_fps=args.fps,
            roi=None,
            backend="dry-run",
            scene=args.scene,
            map_name=args.map_name,
            weapon=args.weapon,
            sensitivity=args.sensitivity,
            fov=args.fov,
            operator_id=args.operator_id,
            notes=args.notes,
            window=None,
            pov_attested=args.attest_pov,
            experiment_attested=args.attest_experiment,
        )
        print(json.dumps({
            "session_id": metadata.session_id,
            "metadata": metadata.extra,
            "duration_s": args.duration,
            "mode": args.mode,
            "note": "dry-run only; no window capture performed",
        }, indent=2, ensure_ascii=False))
        return 0

    try:
        session_dir = _capture(args)
    except KeyboardInterrupt:
        print("[ERROR] capture interrupted; session may be incomplete", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] capture failed: {exc}", file=sys.stderr)
        return 2

    print(f"[INFO] pilot captured: {session_dir}")
    print(f"[INFO] validate: python tools/check_fps_pilot.py \"{session_dir}\" --verify-hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())