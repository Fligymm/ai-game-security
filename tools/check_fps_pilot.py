"""Validate a P0-B first-person POV session.

The checker separates independent evidence:
  FILE_INTEGRITY_VERIFIED, VIDEO_DECODE_VERIFIED, GAME_WINDOW_OBSERVED,
  POV_MANUALLY_ATTESTED, EXPERIMENT_MANUALLY_ATTESTED.

A hash match must not be presented as proof that a human/bot was actually
recorded. Manual attestations remain explicit metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import cv2

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.check_session import check_session


ALLOWED_AGENTS = {"human", "game_bot"}
EXPECTED_CAPTURE_SOURCE = {
    "human": "player_pov",
    "game_bot": "observer_followed_bot",
}
PROTOCOL_VERSION = "anticheat.p0b.v2"
REQUIRED_LIFECYCLE = (
    "session_created",
    "game_window_verified",
    "capture_started",
    "experiment_started",
    "experiment_finished",
    "capture_stopped",
    "manifest_generated",
    "integrity_verified",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_lifecycle(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    if not path.is_file():
        return events, ["missing lifecycle.jsonl"]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return events, [f"cannot read lifecycle.jsonl: {exc}"]
    last_mono: int | None = None
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"lifecycle.jsonl:{line_no}: invalid json: {exc}")
            continue
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            errors.append(f"lifecycle.jsonl:{line_no}: invalid event object")
            continue
        mono = event.get("monotonic_ns")
        if not isinstance(mono, int):
            errors.append(f"lifecycle.jsonl:{line_no}: monotonic_ns is not an int")
        else:
            if last_mono is not None and mono < last_mono:
                errors.append(f"lifecycle.jsonl:{line_no}: monotonic_ns goes backwards")
            last_mono = mono
        events.append(event)
    return events, errors


def _probe_video(path: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    stats: dict[str, Any] = {}
    if not path.is_file() or path.stat().st_size == 0:
        return stats, ["capture video is missing or empty"]
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return stats, ["capture video cannot be opened/decoded"]
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ok, frame = cap.read()
        stats = {
            "frame_count": frame_count,
            "fps": fps,
            "width": width,
            "height": height,
            "duration_s": (frame_count / fps) if fps > 0 else None,
            "first_frame_readable": bool(ok and frame is not None),
        }
        if not ok or frame is None:
            errors.append("capture video has no readable first frame")
        if frame_count <= 0:
            errors.append("capture video frame_count <= 0")
        if fps <= 0:
            errors.append("capture video FPS <= 0")
        if width <= 0 or height <= 0:
            errors.append("capture video resolution is empty")
    finally:
        cap.release()
    return stats, errors


def check_pilot(session_dir: str | Path, *, verify_hash: bool = False) -> dict[str, Any]:
    root = Path(session_dir)
    base = check_session(root, verify_hash=verify_hash)
    errors = list(base.get("errors", []))
    warnings = list(base.get("warnings", []))
    stats = dict(base.get("stats", {}))
    statuses = {
        "FILE_INTEGRITY_VERIFIED": False,
        "VIDEO_DECODE_VERIFIED": False,
        "GAME_WINDOW_OBSERVED": False,
        "POV_MANUALLY_ATTESTED": False,
        "EXPERIMENT_MANUALLY_ATTESTED": False,
        "TIMEBASE_CONSISTENT": False,
    }

    session_path = root / "session.json"
    if not session_path.is_file():
        return {
            "ok": False,
            "session_dir": str(root),
            "errors": errors + ["missing session.json"],
            "warnings": warnings,
            "stats": stats,
            "statuses": statuses,
        }

    session = json.loads(session_path.read_text(encoding="utf-8"))
    extra = session.get("extra", {})
    if not isinstance(extra, dict):
        errors.append("session.extra is not an object")
        extra = {}

    agent_type = extra.get("agent_type")
    if agent_type not in ALLOWED_AGENTS:
        errors.append(
            f"invalid/missing extra.agent_type: {agent_type!r}; "
            f"P0-B capture allows only {sorted(ALLOWED_AGENTS)}"
        )
    if extra.get("view_mode") != "first_person":
        errors.append(f"expected view_mode=first_person, got {extra.get('view_mode')!r}")
    expected_source = EXPECTED_CAPTURE_SOURCE.get(agent_type)
    if expected_source is None or extra.get("capture_source") != expected_source:
        errors.append(
            f"capture_source={extra.get('capture_source')!r} does not match "
            f"agent_type={agent_type!r} expected {expected_source!r}"
        )
    if extra.get("is_proxy") is not False:
        errors.append("P0-B pilot must set extra.is_proxy=false")
    if extra.get("real_control") is not False:
        errors.append("P0-B must set extra.real_control=false")
    if extra.get("capture_mode") != "screen_only":
        errors.append("P0-B pilot must use extra.capture_mode=screen_only")
    if extra.get("protocol_version") != PROTOCOL_VERSION:
        errors.append(
            f"unexpected protocol_version: {extra.get('protocol_version')!r}; "
            f"expected {PROTOCOL_VERSION!r}"
        )
    if not session.get("source"):
        errors.append("missing session.source")
    if session.get("status") != "closed":
        errors.append(f"session status is {session.get('status')!r}, expected 'closed'")

    window = extra.get("window")
    if not isinstance(window, dict) or not window.get("hwnd"):
        errors.append("missing recorded game window metadata")
    else:
        statuses["GAME_WINDOW_OBSERVED"] = True
    if extra.get("pov_attested") is True:
        statuses["POV_MANUALLY_ATTESTED"] = True
    else:
        errors.append("missing explicit pov_attested=true")
    if extra.get("experiment_attested") is True:
        statuses["EXPERIMENT_MANUALLY_ATTESTED"] = True
    else:
        errors.append("missing explicit experiment_attested=true")

    lifecycle, life_errors = _read_lifecycle(root / "lifecycle.jsonl")
    errors.extend(life_errors)
    names = [event.get("event") for event in lifecycle]
    if names:
        if "capture_aborted" in names:
            errors.append("lifecycle contains capture_aborted")
        for required in REQUIRED_LIFECYCLE:
            if required not in names:
                errors.append(f"lifecycle missing event: {required}")
        if "experiment_started" in names and "experiment_finished" in names:
            if names.index("experiment_started") > names.index("experiment_finished"):
                errors.append("lifecycle experiment_started occurs after experiment_finished")
        if "capture_stopped" in names and "manifest_generated" in names:
            if names.index("capture_stopped") > names.index("manifest_generated"):
                errors.append("lifecycle capture_stopped occurs after manifest_generated")
        integrity_events = [event for event in lifecycle if event.get("event") == "integrity_verified"]
        if integrity_events and integrity_events[-1].get("ok") is True and not base.get("errors"):
            statuses["FILE_INTEGRITY_VERIFIED"] = bool(verify_hash)
    if not verify_hash:
        warnings.append("FILE_INTEGRITY_VERIFIED requires --verify-hash")

    video_path = root / "capture.mp4"
    video_stats, video_errors = _probe_video(video_path)
    errors.extend(video_errors)
    stats.update({f"video_{key}": value for key, value in video_stats.items()})
    if not video_errors:
        statuses["VIDEO_DECODE_VERIFIED"] = True
        expected_w = session.get("width")
        expected_h = session.get("height")
        if expected_w and int(expected_w) != int(video_stats["width"]):
            errors.append(f"video width {video_stats['width']} != session width {expected_w}")
        if expected_h and int(expected_h) != int(video_stats["height"]):
            errors.append(f"video height {video_stats['height']} != session height {expected_h}")
        if video_stats["duration_s"] is not None:
            session_duration = float(session.get("duration_s") or 0.0)
            if session_duration <= 0:
                errors.append("session duration is not positive")
            elif abs(video_stats["duration_s"] - session_duration) > max(2.0, 0.2 * session_duration):
                errors.append(
                    f"video duration {video_stats['duration_s']:.2f}s differs from "
                    f"session duration {session_duration:.2f}s; "
                    "re-record with a lower --fps or preserve event timestamps"
                )
                statuses["TIMEBASE_CONSISTENT"] = False
            else:
                statuses["TIMEBASE_CONSISTENT"] = True
        video_sha = _sha256(video_path)
        stats["video_sha256"] = video_sha
        artifact = [event for event in lifecycle if event.get("event") == "video_artifact"]
        if not artifact:
            errors.append("lifecycle missing video_artifact hash record")
        elif artifact[-1].get("sha256") != video_sha:
            errors.append("lifecycle video_artifact sha256 does not match capture.mp4")

    stats["agent_type"] = agent_type
    stats["view_mode"] = extra.get("view_mode")
    stats["capture_source"] = extra.get("capture_source")
    stats["protocol_version"] = extra.get("protocol_version")
    stats["scene"] = extra.get("scene")
    stats["map"] = extra.get("map")

    ok = not errors and all(statuses.values())
    return {
        "ok": ok,
        "session_dir": str(root),
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
        "statuses": statuses,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a P0-B first-person POV session")
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--verify-hash", action="store_true")
    args = parser.parse_args(argv)

    result = check_pilot(args.session_dir, verify_hash=args.verify_hash)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())