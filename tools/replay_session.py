"""Replay a SessionRecorder capture with detections, selection, and timestamps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _events(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _frame_iterator(session_dir: Path, session: dict[str, Any], events: list[dict[str, Any]]) -> Iterator[np.ndarray]:
    mode = session.get("record_mode")
    if mode == "video":
        cap = cv2.VideoCapture(str(session_dir / "capture.mp4"))
        if not cap.isOpened():
            raise RuntimeError("capture.mp4 could not be opened")
        try:
            for _ in events:
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("capture.mp4 ended before events.jsonl")
                yield frame
        finally:
            cap.release()
    elif mode == "frames":
        for event in events:
            path = session_dir / "frames" / f"frame_{int(event['record_index']):06d}.jpg"
            frame = cv2.imread(str(path))
            if frame is None:
                raise RuntimeError(f"could not read {path}")
            yield frame
    else:
        raise ValueError(f"unknown record_mode {mode!r}")


def _draw(frame: np.ndarray, event: dict[str, Any], *, session_id: str, elapsed_s: float) -> np.ndarray:
    canvas = frame.copy()
    for det in event.get("detections", []):
        x1, y1, x2, y2 = (int(round(float(det[key]))) for key in ("x1", "y1", "x2", "y2"))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 220, 0), 1)
        label = f"c{det.get('class_id')} {float(det.get('confidence', 0.0)):.2f}"
        cv2.putText(canvas, label, (x1, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 220, 0), 1, cv2.LINE_AA)

    selected = event.get("selected")
    if selected:
        x1, y1, x2, y2 = (int(round(float(selected[key]))) for key in ("x1", "y1", "x2", "y2"))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.circle(canvas, ((x1 + x2) // 2, (y1 + y2) // 2), 3, (0, 0, 255), -1)

    trajectory = (event.get("extra") or {}).get("trajectory")
    if trajectory and len(trajectory.get("points", [])) >= 2:
        center_x, center_y = canvas.shape[1] // 2, canvas.shape[0] // 2
        points = [
            (int(round(center_x + float(point[0]))), int(round(center_y + float(point[1]))))
            for point in trajectory["points"]
        ]
        cv2.polylines(canvas, [np.array(points, dtype=np.int32)], False, (255, 0, 255), 1, cv2.LINE_AA)

    mouse = event.get("mouse_delta")
    applied = "APPLIED" if event.get("applied_mouse") else "dry-run"
    mouse_text = f"delta=({mouse[0]:.1f},{mouse[1]:.1f})" if mouse else "delta=None"
    lines = [
        f"{session_id}  t={elapsed_s:.3f}s  frame={event.get('frame_id')}",
        f"{applied}  {mouse_text}  selected={bool(selected)}",
    ]
    for index, text in enumerate(lines):
        cv2.putText(
            canvas,
            text,
            (6, 16 + index * 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return canvas


def render_session(
    session_dir: str | Path,
    output_path: str | Path,
    *,
    limit: int | None = None,
) -> Path:
    root = Path(session_dir)
    session = _read_json(root / "session.json")
    events = _events(root / "events.jsonl")
    if not events:
        raise ValueError("events.jsonl is empty")
    if limit is not None:
        events = events[: max(0, int(limit))]
    if not events:
        raise ValueError("no events selected for replay")

    fps = float(session.get("video_fps") or 30)
    writer: Any = None
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    first_ts = int(events[0]["timestamp_ns"])
    try:
        for frame, event in zip(_frame_iterator(root, session, events), events):
            if writer is None:
                height, width = frame.shape[:2]
                writer = cv2.VideoWriter(
                    str(output),
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    fps,
                    (width, height),
                )
                if not writer.isOpened():
                    raise RuntimeError("could not create replay video; check OpenCV MP4 support")
            elapsed_s = (int(event["timestamp_ns"]) - first_ts) / 1_000_000_000
            writer.write(_draw(frame, event, session_id=str(session.get("session_id")), elapsed_s=elapsed_s))
    finally:
        if writer is not None:
            writer.release()
    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("replay video was not written")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a capture replay with boxes and timestamps")
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    output = render_session(args.session_dir, args.output, limit=args.limit)
    print(output)


if __name__ == "__main__":
    main()