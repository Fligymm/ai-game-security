"""Validate one multimodal capture session produced by SessionRecorder.

Usage:
    python tools/check_session.py runs/captures/<session>
    python tools/check_session.py runs/captures/<session> --verify-hash
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_session(session_dir: str | Path, *, verify_hash: bool = False) -> dict[str, Any]:
    root = Path(session_dir)
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {}

    session_path = root / "session.json"
    events_path = root / "events.jsonl"
    manifest_path = root / "manifest.json"
    for path in (session_path, events_path, manifest_path):
        if not path.exists():
            errors.append(f"missing {path.name}")
    if errors:
        return {"ok": False, "session_dir": str(root), "errors": errors, "warnings": warnings, "stats": stats}

    session = _read_json(session_path)
    manifest = _read_json(manifest_path)
    events: list[dict[str, Any]] = []
    for line_no, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"events.jsonl:{line_no}: invalid json: {exc}")
            continue
        if not isinstance(event, dict):
            errors.append(f"events.jsonl:{line_no}: event is not an object")
            continue
        events.append(event)

    if session.get("schema_version") != "multimodal.session.v0":
        errors.append(f"unexpected session schema: {session.get('schema_version')!r}")
    if manifest.get("schema_version") != "multimodal.manifest.v0":
        errors.append(f"unexpected manifest schema: {manifest.get('schema_version')!r}")
    if session.get("status") != "closed":
        errors.append(f"session status is {session.get('status')!r}, expected 'closed'")

    seen = int(session.get("frames_seen", -1))
    recorded = int(session.get("frames_recorded", -1))
    skipped = int(session.get("frames_skipped", -1))
    if seen != recorded + skipped:
        errors.append(f"frame counts inconsistent: seen={seen}, recorded={recorded}, skipped={skipped}")
    if recorded != len(events):
        errors.append(f"events count {len(events)} != frames_recorded {recorded}")

    counts = manifest.get("counts", {})
    for key, value in (("frames_seen", seen), ("frames_recorded", recorded), ("frames_skipped", skipped)):
        if counts.get(key) != value:
            errors.append(f"manifest.counts.{key}={counts.get(key)!r} != session {value}")

    last_timestamp: int | None = None
    last_frame_id: int | None = None
    for index, event in enumerate(events):
        if event.get("frame_id") is None or event.get("record_index") != index:
            errors.append(f"event {index}: bad frame_id/record_index")
        try:
            frame_id = int(event.get("frame_id", -1))
        except (TypeError, ValueError):
            errors.append(f"event {index}: frame_id is not an int")
            frame_id = -1
        if last_frame_id is not None and frame_id <= last_frame_id:
            errors.append(f"event {index}: frame_id is not increasing ({last_frame_id} -> {frame_id})")
        last_frame_id = frame_id
        timestamp = event.get("timestamp_ns")
        if not isinstance(timestamp, int):
            errors.append(f"event {index}: timestamp_ns is not an int")
        else:
            if last_timestamp is not None and timestamp < last_timestamp:
                errors.append(f"event {index}: timestamp goes backwards")
            last_timestamp = timestamp
        if not isinstance(event.get("detections"), list):
            errors.append(f"event {index}: detections is not a list")
        if not isinstance(event.get("applied_mouse"), bool):
            errors.append(f"event {index}: applied_mouse is not a bool")

    mode = session.get("record_mode")
    if mode == "video":
        video = root / "capture.mp4"
        if not video.exists() or video.stat().st_size == 0:
            errors.append("capture.mp4 is missing or empty")
        else:
            cap = cv2.VideoCapture(str(video))
            try:
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            finally:
                cap.release()
            stats["video_frames"] = frame_count
            if frame_count <= 0:
                errors.append("capture.mp4 has no decodable frames")
            elif frame_count != recorded:
                warnings.append(f"video frame count {frame_count} != recorded {recorded}")
    elif mode == "frames":
        frame_dir = root / "frames"
        files = sorted(frame_dir.glob("*.jpg")) if frame_dir.exists() else []
        stats["frame_files"] = len(files)
        if len(files) != recorded:
            errors.append(f"frame files {len(files)} != frames_recorded {recorded}")
    else:
        errors.append(f"unknown record_mode {mode!r}")

    files = manifest.get("files", [])
    if not isinstance(files, list) or not files:
        errors.append("manifest.files is missing or empty")
    for item in files:
        if not isinstance(item, dict):
            errors.append("manifest.files contains a non-object")
            continue
        relative = Path(str(item.get("path", "")))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            errors.append(f"unsafe manifest path: {relative}")
            continue
        file_path = root / relative
        if not file_path.is_file():
            errors.append(f"manifest file missing: {relative}")
            continue
        expected_bytes = item.get("bytes")
        if isinstance(expected_bytes, int) and file_path.stat().st_size != expected_bytes:
            errors.append(f"size mismatch for {relative}")
        expected_hash = item.get("sha256")
        if verify_hash and expected_hash:
            if _sha256(file_path) != expected_hash:
                errors.append(f"sha256 mismatch for {relative}")
        elif verify_hash and not expected_hash:
            warnings.append(f"no sha256 for {relative}")

    duration_s = float(session.get("duration_s") or 0.0)
    effective_fps = (recorded / duration_s) if duration_s > 0 else None
    if effective_fps is not None and effective_fps < 20:
        warnings.append(f"effective_fps {effective_fps:.1f} is below the pilot floor of 20")

    stats.update(
        {
            "session_id": session.get("session_id"),
            "source": session.get("source"),
            "record_mode": mode,
            "events": len(events),
            "duration_s": session.get("duration_s"),
            "effective_fps": round(effective_fps, 1) if effective_fps is not None else None,
            "frames_seen": seen,
            "frames_recorded": recorded,
            "frames_skipped": skipped,
            "selected_frames": sum(1 for event in events if event.get("selected")),
            "applied_frames": sum(1 for event in events if event.get("applied_mouse") is True),
        }
    )
    return {"ok": not errors, "session_dir": str(root), "errors": errors, "warnings": warnings, "stats": stats}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a SessionRecorder capture")
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--verify-hash", action="store_true", help="Recompute sha256 for every manifest file")
    args = parser.parse_args()
    report = check_session(args.session_dir, verify_hash=args.verify_hash)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()