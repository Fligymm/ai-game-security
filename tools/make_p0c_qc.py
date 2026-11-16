"""Create deterministic contact sheets for P0-C target/track QC.

Reads one or more tiled inference output directories and their source videos;
writes a contact sheet plus a JSON list of the sampled frames. Source videos
are not modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_records(path: Path) -> list[dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records.sort(key=lambda item: int(item.get("frame_index", 0)))
    return records


def _pick(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected = [r for r in records if r.get("selected")]
    if not selected:
        return []
    priority = []
    # Include track switches, head selections, and evenly spaced selected frames.
    priority.extend(r for r in selected if r.get("selected", {}).get("track_id") is not None and r.get("selected", {}).get("class_id") == 0)
    priority.extend(
        r for r in selected
        if any(d.get("class_id") == 0 for d in r.get("detections", []))
    )
    step = max(1, len(selected) // max(limit, 1))
    priority.extend(selected[::step])
    seen = set()
    result = []
    for record in priority:
        idx = int(record["frame_index"])
        if idx in seen:
            continue
        seen.add(idx)
        result.append(record)
        if len(result) >= limit:
            break
    return result


def _draw(frame, record: dict[str, Any]) -> np.ndarray:
    canvas = frame.copy()
    selected = record.get("selected")
    selected_track = selected.get("track_id") if isinstance(selected, dict) else None
    for det in record.get("detections", []):
        cls = int(det.get("class_id", -1))
        color = (255, 180, 40) if cls == 0 else (40, 200, 80)
        x1, y1, x2, y2 = (int(det[k]) for k in ("x1", "y1", "x2", "y2"))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        label = f"{'head' if cls == 0 else 'body'} {det.get('confidence', 0):.2f} id={det.get('track_id')}"
        cv2.putText(canvas, label, (x1, max(14, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    if isinstance(selected, dict):
        x1, y1, x2, y2 = (int(selected[k]) for k in ("x1", "y1", "x2", "y2"))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 230, 255), 3)
    text = (
        f"frame={record.get('frame_index')} t={record.get('capture_time_s')} "
        f"selected={selected.get('class_name') if selected else None} "
        f"id={selected_track} switch={record.get('track_switched')}"
    )
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 28), (0, 0, 0), -1)
    cv2.putText(canvas, text, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def make_sheet(session_dir: Path, output_dir: Path, *, limit: int = 20) -> dict[str, Any]:
    meta = json.loads((session_dir / "inference_meta.json").read_text(encoding="utf-8"))
    records = _load_records(session_dir / "inference_frames.jsonl")
    chosen = _pick(records, limit)
    if not chosen:
        raise RuntimeError(f"no selected frames in {session_dir}")
    video_path = Path(meta["source_video"])
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open source video: {video_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    thumbs = []
    sample_rows = []
    try:
        for record in chosen:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(record["frame_index"]))
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            canvas = _draw(frame, record)
            thumb = cv2.resize(canvas, (480, 270), interpolation=cv2.INTER_AREA)
            thumbs.append(thumb)
            sample_rows.append(
                {
                    "frame_index": record.get("frame_index"),
                    "capture_time_s": record.get("capture_time_s"),
                    "video_time_s": record.get("video_time_s"),
                    "selected_class": record.get("selected", {}).get("class_name") if record.get("selected") else None,
                    "selected_track_id": record.get("selected", {}).get("track_id") if record.get("selected") else None,
                    "track_switched": record.get("track_switched"),
                    "num_detections": len(record.get("detections", [])),
                }
            )
    finally:
        capture.release()

    columns = 4
    rows = max(1, (len(thumbs) + columns - 1) // columns)
    sheet = np.zeros((rows * 270, columns * 480, 3), dtype=np.uint8)
    for index, thumb in enumerate(thumbs):
        row, col = divmod(index, columns)
        sheet[row * 270 : (row + 1) * 270, col * 480 : (col + 1) * 480] = thumb
    stem = f"contact_sheet_{meta.get('source_agent_type', 'unknown')}.jpg"
    output_path = output_dir / stem
    cv2.imwrite(str(output_path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
    (output_dir / f"qc_samples_{meta.get('source_agent_type', 'unknown')}.json").write_text(
        json.dumps({"source_session_id": meta.get("source_session_id"), "samples": sample_rows}, indent=2),
        encoding="utf-8",
    )
    return {"contact_sheet": str(output_path), "samples": len(sample_rows)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create P0-C QC contact sheets")
    parser.add_argument("session_dirs", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    for session_dir in args.session_dirs:
        try:
            result = make_sheet(session_dir, args.output_dir, limit=args.limit)
            print(f"{session_dir.name}: {result}")
        except Exception as exc:
            print(f"[ERROR] {session_dir}: {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())