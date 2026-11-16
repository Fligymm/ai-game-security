"""Extract descriptive P0-C features from tiled CV-Agent dry-run outputs.

This is a pilot analysis, not a classifier. It reads inference_frames.jsonl
produced by tools/run_cv_agent_offline.py and summarizes screen-only visual
behavior: detection coverage, selected-target episodes, track switching, and
controller-offset magnitudes.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_records(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    records.sort(key=lambda item: int(item.get("frame_index", 0)))
    return records


def _episodes(flags: list[bool], times: list[float | None]) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    start: int | None = None
    for index, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            end = index
            begin_t = times[start] if start < len(times) else None
            end_t = times[end - 1] if end - 1 < len(times) else None
            episodes.append(
                {
                    "start_frame": start,
                    "end_frame": end,
                    "duration_s": (float(end_t) - float(begin_t)) if begin_t is not None and end_t is not None else None,
                }
            )
            start = None
    return episodes


def _offset_magnitude(record: dict[str, Any]) -> float | None:
    offset = record.get("compensated_offset")
    if not isinstance(offset, (list, tuple)) or len(offset) != 2:
        return None
    try:
        return float(np.hypot(float(offset[0]), float(offset[1])))
    except (TypeError, ValueError):
        return None


def _selected_class(record: dict[str, Any]) -> str | None:
    selected = record.get("selected")
    if not isinstance(selected, dict):
        return None
    name = selected.get("class_name")
    if name:
        return str(name)
    class_id = selected.get("class_id")
    return "enemy_head" if class_id == 0 else ("enemy_body" if class_id == 1 else str(class_id))


def frame_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_track: int | None = None
    for record in records:
        selected = record.get("selected") if isinstance(record.get("selected"), dict) else None
        detections = record.get("detections") if isinstance(record.get("detections"), list) else []
        selected_track = selected.get("track_id") if selected else None
        rows.append(
            {
                "frame_index": int(record.get("frame_index", 0)),
                "video_time_s": record.get("video_time_s"),
                "capture_time_s": record.get("capture_time_s"),
                "num_detections": len(detections),
                "num_heads": sum(1 for det in detections if det.get("class_id") == 0),
                "num_bodies": sum(1 for det in detections if det.get("class_id") == 1),
                "selected": selected is not None,
                "selected_class": _selected_class(record),
                "selected_track_id": selected_track,
                "track_switched": bool(selected is not None and selected_track is not None and previous_track is not None and selected_track != previous_track),
                "selected_confidence": (selected.get("confidence") if selected else None),
                "offset_px": _offset_magnitude(record),
                "applied_mouse": bool(record.get("applied_mouse", False)),
            }
        )
        if selected is not None and selected_track is not None:
            previous_track = int(selected_track)
    return rows


def summarize_session(meta: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    capture_times = [row.get("capture_time_s") for row in rows if isinstance(row.get("capture_time_s"), (int, float))]
    selected_flags = [bool(row["selected"]) for row in rows]
    selected_rows = [row for row in rows if row["selected"]]
    offsets = [float(row["offset_px"]) for row in selected_rows if row.get("offset_px") is not None]
    confidences = [float(row["selected_confidence"]) for row in selected_rows if isinstance(row.get("selected_confidence"), (int, float))]
    detection_counts = [int(row["num_detections"]) for row in rows]
    episodes = _episodes(selected_flags, [row.get("capture_time_s") for row in rows])
    gaps = []
    for previous, current in zip(episodes, episodes[1:]):
        if previous["duration_s"] is not None and current["duration_s"] is not None:
            gaps.append(max(0.0, (current.get("start_frame", 0) - previous.get("end_frame", 0)) / max(len(rows) - 1, 1) * (capture_times[-1] if capture_times else 0.0)))
    track_ids = [row["selected_track_id"] for row in selected_rows if row.get("selected_track_id") is not None]
    class_counts: dict[str, int] = {}
    for row in selected_rows:
        name = row.get("selected_class") or "unknown"
        class_counts[name] = class_counts.get(name, 0) + 1

    return {
        "source_session_id": meta.get("source_session_id"),
        "agent_type": meta.get("source_agent_type"),
        "capture_source": meta.get("source_capture_source"),
        "view_mode": meta.get("source_view_mode"),
        "model_sha256": meta.get("model_sha256"),
        "source_video_sha256": meta.get("source_video_sha256"),
        "dry_run": meta.get("dry_run"),
        "real_control": meta.get("real_control"),
        "apply_mouse": meta.get("apply_mouse"),
        "frames": len(rows),
        "detection_frames": sum(1 for count in detection_counts if count > 0),
        "selected_frames": len(selected_rows),
        "detection_frame_ratio": (sum(1 for count in detection_counts if count > 0) / len(rows)) if rows else 0.0,
        "selected_frame_ratio": (len(selected_rows) / len(rows)) if rows else 0.0,
        "mean_detections_per_frame": float(np.mean(detection_counts)) if detection_counts else 0.0,
        "selected_class_counts": class_counts,
        "unique_selected_tracks": len(set(track_ids)),
        "track_switches": int(sum(1 for row in rows if row.get("track_switched"))),
        "acquisition_episodes": len(episodes),
        "selected_episode_duration_mean_s": (
            float(np.mean([ep["duration_s"] for ep in episodes if ep["duration_s"] is not None]))
            if episodes else 0.0
        ),
        "selected_episode_duration_max_s": (
            float(np.max([ep["duration_s"] for ep in episodes if ep["duration_s"] is not None]))
            if episodes else 0.0
        ),
        "mean_offset_px": float(np.mean(offsets)) if offsets else None,
        "median_offset_px": float(np.median(offsets)) if offsets else None,
        "p95_offset_px": float(np.percentile(offsets, 95)) if offsets else None,
        "mean_selected_confidence": float(np.mean(confidences)) if confidences else None,
        "capture_duration_s": (max(capture_times) - min(capture_times)) if capture_times else None,
        "all_applied_false": all(row["applied_mouse"] is False for row in rows),
        "episodes": episodes,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def extract(session_dirs: list[Path], output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)

    summaries = []
    all_frames = []
    sources = []
    for session_dir in session_dirs:
        meta = _load_json(session_dir / "inference_meta.json")
        records = _load_records(session_dir / "inference_frames.jsonl")
        if meta.get("dry_run") is not True or meta.get("real_control") is not False or meta.get("apply_mouse") is not False:
            raise ValueError(f"not a dry-run output: {session_dir}")
        rows = frame_rows(records)
        for row in rows:
            row["session"] = meta.get("source_session_id")
            row["agent_type"] = meta.get("source_agent_type")
        all_frames.extend(rows)
        summaries.append(summarize_session(meta, rows))
        sources.append(
            {
                "session_dir": str(session_dir),
                "source_session_id": meta.get("source_session_id"),
                "source_video_sha256": meta.get("source_video_sha256"),
                "model_sha256": meta.get("model_sha256"),
            }
        )

    _write_csv(
        output_dir / "frames.csv",
        all_frames,
        list(all_frames[0].keys()) if all_frames else ["session", "frame_index"],
    )
    _write_csv(
        output_dir / "session_summary.csv",
        summaries,
        list(summaries[0].keys()) if summaries else ["source_session_id"],
    )
    report = {
        "schema_version": "anticheat.p0c_feature_pilot.v1",
        "descriptive_only": True,
        "sources": sources,
        "summaries": summaries,
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract descriptive P0-C features from tiled inference outputs")
    parser.add_argument("session_dirs", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = extract(args.session_dirs, args.output_dir)
    except Exception as exc:
        print(f"[ERROR] feature extraction failed: {exc}", file=sys.stderr)
        return 2
    print(f"[INFO] feature output: {args.output_dir}")
    for summary in report["summaries"]:
        print(
            f"{summary['source_session_id']} agent={summary['agent_type']} "
            f"detected={summary['detection_frame_ratio']:.1%} "
            f"selected={summary['selected_frame_ratio']:.1%} "
            f"episodes={summary['acquisition_episodes']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())