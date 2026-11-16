"""P0-C Feature v2 extraction from old-model tiled inference records.

Feature v2 is episode-aware: visible and selected runs are segmented by time,
then acquisition, tracking, correction, switching, and visibility features are
computed without using raw session length/count identity features.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


GAP_S = 0.15
FEATURE_NAMES = [
    "acq_delay_mean_s",
    "acq_delay_median_s",
    "acq_delay_ratio_mean",
    "pre_select_visible_ratio",
    "offset_mean_norm",
    "offset_median_norm",
    "offset_cv",
    "offset_slope",
    "settling_time_mean_s",
    "jitter_ratio",
    "sign_flip_rate",
    "correction_magnitude_mean_norm",
    "overshoot_proxy_rate",
    "path_efficiency_mean",
    "trajectory_straightness_mean",
    "track_switch_rate_per_s",
    "head_body_switch_rate",
    "reacquire_gap_mean_s",
    "switch_overlap_ratio",
    "visible_duration_median_s",
    "visible_fraction",
    "selected_fraction_of_visible",
    "target_area_median_norm",
    "target_confidence_mean",
    "occlusion_gap_mean_s",
]


def _load_records(path: Path) -> list[dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records.sort(key=lambda row: int(row.get("frame_index", 0)))
    return records


def _time(record: dict[str, Any], fallback_fps: float) -> float:
    value = record.get("capture_time_s")
    if isinstance(value, (int, float)):
        return float(value)
    video = record.get("video_time_s")
    if isinstance(video, (int, float)):
        return float(video)
    return float(record.get("frame_index", 0)) / max(fallback_fps, 1e-9)


def _runs(flags: list[bool], times: list[float], gap_s: float = GAP_S) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    start: int | None = None
    for index, flag in enumerate(flags + [False]):
        if flag:
            if start is None:
                start = index
            elif times[index] - times[index - 1] > gap_s:
                runs.append(_run(start, index, times))
                start = index
        elif start is not None:
            runs.append(_run(start, index, times))
            start = None
    return runs


def _run(start: int, end: int, times: list[float]) -> dict[str, Any]:
    return {
        "start_idx": int(start),
        "end_idx": int(end),
        "start_s": float(times[start]),
        "end_s": float(times[end - 1]),
        "duration_s": max(0.0, float(times[end - 1]) - float(times[start])),
        "frames": int(end - start),
    }


def _selected_box(record: dict[str, Any]) -> tuple[float, float, float, float] | None:
    selected = record.get("selected")
    if not isinstance(selected, dict):
        return None
    try:
        return float(selected["x1"]), float(selected["y1"]), float(selected["x2"]), float(selected["y2"])
    except (KeyError, TypeError, ValueError):
        return None


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _offset(record: dict[str, Any]) -> tuple[float, float] | None:
    value = record.get("compensated_offset")
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def _median(values: list[float]) -> float:
    return float(np.median(values)) if values else 0.0


def extract_session(session_dir: Path) -> tuple[dict[str, float], list[dict[str, Any]], dict[str, Any]]:
    meta = json.loads((session_dir / "inference_meta.json").read_text(encoding="utf-8"))
    records = _load_records(session_dir / "inference_frames.jsonl")
    if not records:
        raise ValueError(f"no inference records: {session_dir}")
    config = meta.get("config", {})
    fps = float(config.get("video_fps") or 30.0)
    times = [_time(record, fps) for record in records]
    width = float(config.get("video_width") or 1920)
    height = float(config.get("video_height") or 1080)
    scene_diag = math.hypot(width, height)

    visible_flags = [bool(record.get("detections")) for record in records]
    selected_flags = [isinstance(record.get("selected"), dict) for record in records]
    visible_runs = _runs(visible_flags, times)
    selected_runs = _runs(selected_flags, times)

    selected_offset_values: list[float] = []
    selected_offset_deltas: list[float] = []
    selected_centers: list[tuple[float, float]] = []
    selected_boxes: list[tuple[float, float, float, float]] = []
    selected_conf: list[float] = []
    selected_classes: list[int] = []
    selected_tracks: list[int | None] = []
    selected_times: list[float] = []
    traj_straightness: list[float] = []
    acq_delays: list[float] = []
    acq_ratios: list[float] = []
    pre_select_ratios: list[float] = []
    settling_times: list[float] = []
    jitter_values: list[float] = []
    overshoot_flags: list[float] = []

    for run in selected_runs:
        start, end = run["start_idx"], run["end_idx"]
        sel_times = times[start:end]
        offsets = []
        centers = []
        boxes = []
        classes = []
        tracks = []
        for record in records[start:end]:
            selected = record.get("selected") if isinstance(record.get("selected"), dict) else {}
            box = _selected_box(record)
            if box is not None:
                boxes.append(box)
                centers.append(((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0))
                diag = math.hypot(box[2] - box[0], box[3] - box[1])
                norm = diag if diag > 1e-9 else scene_diag
                off = _offset(record)
                if off is not None:
                    offsets.append((off[0], off[1], math.hypot(off[0], off[1]) / norm))
            try:
                selected_conf.append(float(selected.get("confidence")))
            except (TypeError, ValueError):
                pass
            try:
                classes.append(int(selected.get("class_id")))
            except (TypeError, ValueError):
                classes.append(-1)
            track = selected.get("track_id")
            tracks.append(int(track) if isinstance(track, (int, float)) else None)
            try:
                traj_straightness.append(float(record.get("features", {}).get("straightness")))
            except (TypeError, ValueError):
                pass
        if not offsets:
            continue
        selected_times.extend(sel_times)
        selected_boxes.extend(boxes)
        selected_centers.extend(centers)
        selected_classes.extend(classes)
        selected_tracks.extend(tracks)
        selected_offset_values.extend(item[2] for item in offsets)
        if len(offsets) >= 2:
            selected_offset_deltas.extend(
                math.hypot(offsets[i][0] - offsets[i - 1][0], offsets[i][1] - offsets[i - 1][1]) / scene_diag
                for i in range(1, len(offsets))
            )
        # F1: align selected run to the containing/preceding visible run.
        containing = [
            visible for visible in visible_runs
            if visible["start_idx"] <= start < visible["end_idx"]
        ]
        visible = containing[0] if containing else None
        if visible is None:
            before = [v for v in visible_runs if v["end_idx"] <= start]
            visible = before[-1] if before else None
        if visible is not None:
            delay = max(0.0, run["start_s"] - visible["start_s"])
            acq_delays.append(delay)
            if visible["duration_s"] > 1e-9:
                acq_ratios.append(min(1.0, delay / visible["duration_s"]))
            visible_frames = max(visible["frames"], 1)
            pre_select_ratios.append(min(1.0, max(0, start - visible["start_idx"]) / visible_frames))
        # F2: settling and jitter.
        run_offsets = [item[2] for item in offsets]
        med = _median(run_offsets)
        settle = run["duration_s"]
        if med > 0:
            for i, value in enumerate(run_offsets):
                if value <= med * 0.5:
                    settle = sel_times[i] - run["start_s"]
                    break
        settling_times.append(max(0.0, settle))
        if len(run_offsets) >= 2:
            jitter_values.append(float(np.mean(np.abs(np.diff(run_offsets)))) / max(med, 1e-9))
        # F3: overshoot proxy: offset rises after a lower value inside the run.
        overshoot = 0.0
        if len(run_offsets) >= 3:
            running_min = run_offsets[0]
            for value in run_offsets[1:]:
                if value > running_min * 1.25 + 1e-6:
                    overshoot = 1.0
                    break
                running_min = min(running_min, value)
        overshoot_flags.append(overshoot)

    # Track/class switching and overlap churn.
    track_switches = 0
    class_switches = 0
    overlap_switches = 0
    for i in range(1, len(selected_tracks)):
        if selected_tracks[i] is not None and selected_tracks[i - 1] is not None and selected_tracks[i] != selected_tracks[i - 1]:
            track_switches += 1
            if i < len(selected_boxes) and _iou(selected_boxes[i - 1], selected_boxes[i]) >= 0.3:
                overlap_switches += 1
        if selected_classes[i] >= 0 and selected_classes[i - 1] >= 0 and selected_classes[i] != selected_classes[i - 1]:
            class_switches += 1

    selected_duration = max(0.0, (selected_times[-1] - selected_times[0])) if len(selected_times) >= 2 else 0.0
    gaps = []
    if len(selected_runs) >= 2:
        for previous, current in zip(selected_runs, selected_runs[1:]):
            gaps.append(max(0.0, current["start_s"] - previous["end_s"]))
    visible_gaps = [
        max(0.0, current["start_s"] - previous["end_s"])
        for previous, current in zip(visible_runs, visible_runs[1:])
    ]

    # Path efficiency and correction magnitude.
    path_efficiency = 0.0
    if len(selected_centers) >= 2:
        displacement = math.hypot(
            selected_centers[-1][0] - selected_centers[0][0],
            selected_centers[-1][1] - selected_centers[0][1],
        )
        path_len = sum(
            math.hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(selected_centers, selected_centers[1:])
        )
        path_efficiency = displacement / path_len if path_len > 1e-9 else 0.0

    area_norms = []
    for box in selected_boxes:
        area_norms.append(max(0.0, (box[2] - box[0]) * (box[3] - box[1])) / max(width * height, 1.0))

    sign_flips = 0
    # Recompute sign flips from raw offsets with a compact pass.
    raw_offsets = [
        _offset(record)
        for record in records
        if isinstance(record.get("selected"), dict)
    ]
    raw_offsets = [item for item in raw_offsets if item is not None]
    for (x1, y1), (x2, y2) in zip(raw_offsets, raw_offsets[1:]):
        if x1 * x2 < 0 or y1 * y2 < 0:
            sign_flips += 1

    features = {
        "acq_delay_mean_s": float(np.mean(acq_delays)) if acq_delays else 0.0,
        "acq_delay_median_s": _median(acq_delays),
        "acq_delay_ratio_mean": float(np.mean(acq_ratios)) if acq_ratios else 0.0,
        "pre_select_visible_ratio": float(np.mean(pre_select_ratios)) if pre_select_ratios else 0.0,
        "offset_mean_norm": float(np.mean(selected_offset_values)) if selected_offset_values else 0.0,
        "offset_median_norm": _median(selected_offset_values),
        "offset_cv": (
            float(np.std(selected_offset_values) / max(np.mean(selected_offset_values), 1e-9))
            if selected_offset_values else 0.0
        ),
        "offset_slope": _safe_slope(selected_times, selected_offset_values),
        "settling_time_mean_s": float(np.mean(settling_times)) if settling_times else 0.0,
        "jitter_ratio": float(np.mean(jitter_values)) if jitter_values else 0.0,
        "sign_flip_rate": sign_flips / max(len(selected_offset_values), 1),
        "correction_magnitude_mean_norm": (
            float(np.mean(selected_offset_deltas)) / max(_median(selected_offset_values), 1e-9)
            if selected_offset_deltas else 0.0
        ),
        "overshoot_proxy_rate": float(np.mean(overshoot_flags)) if overshoot_flags else 0.0,
        "path_efficiency_mean": path_efficiency,
        "trajectory_straightness_mean": float(np.mean(traj_straightness)) if traj_straightness else 0.0,
        "track_switch_rate_per_s": track_switches / max(selected_duration, 1e-9) if selected_duration else 0.0,
        "head_body_switch_rate": class_switches / max(len(selected_classes), 1),
        "reacquire_gap_mean_s": float(np.mean(gaps)) if gaps else 0.0,
        "switch_overlap_ratio": overlap_switches / max(track_switches, 1) if track_switches else 0.0,
        "visible_duration_median_s": _median([run["duration_s"] for run in visible_runs]),
        "visible_fraction": sum(visible_flags) / max(len(records), 1),
        "selected_fraction_of_visible": sum(selected_flags) / max(sum(visible_flags), 1),
        "target_area_median_norm": _median(area_norms),
        "target_confidence_mean": float(np.mean(selected_conf)) if selected_conf else 0.0,
        "occlusion_gap_mean_s": float(np.mean(visible_gaps)) if visible_gaps else 0.0,
    }
    episode_rows = []
    for run in selected_runs:
        episode_rows.append({
            "start_idx": run["start_idx"],
            "end_idx": run["end_idx"],
            "start_s": run["start_s"],
            "end_s": run["end_s"],
            "duration_s": run["duration_s"],
            "frames": run["frames"],
        })
    return features, episode_rows, meta


def _safe_slope(times: list[float], values: list[float]) -> float:
    if len(times) < 2 or len(values) != len(times):
        return 0.0
    t = np.asarray(times, dtype=float)
    v = np.asarray(values, dtype=float)
    t = t - t[0]
    denom = float(np.dot(t, t))
    return float(np.dot(t, v - np.mean(v)) / denom) if denom > 1e-12 else 0.0


def extract(session_dirs: list[Path], output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    rows = []
    episodes = []
    sources = []
    for session_dir in session_dirs:
        features, episode_rows, meta = extract_session(session_dir)
        session_id = meta.get("source_session_id")
        agent = meta.get("source_agent_type")
        row = {
            "session_id": session_id,
            "agent_type": agent,
            **features,
        }
        rows.append(row)
        for ep in episode_rows:
            ep.update({"session_id": session_id, "agent_type": agent})
            episodes.append(ep)
        sources.append({
            "session_dir": str(session_dir),
            "session_id": session_id,
            "agent_type": agent,
            "source_video_sha256": meta.get("source_video_sha256"),
            "model_sha256": meta.get("model_sha256"),
        })
    with (output_dir / "features_v2.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["session_id", "agent_type", *FEATURE_NAMES])
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "episodes_v2.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["session_id", "agent_type", "start_idx", "end_idx", "start_s", "end_s", "duration_s", "frames"])
        writer.writeheader()
        writer.writerows(episodes)
    payload = {
        "schema_version": "anticheat.p0c_features_v2.v1",
        "feature_names": FEATURE_NAMES,
        "sources": sources,
        "rows": len(rows),
    }
    (output_dir / "features_v2_meta.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract P0-C Feature v2 from old tiled inference outputs")
    parser.add_argument("session_dirs", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        config = extract(args.session_dirs, args.output_dir)
    except Exception as exc:
        print(f"[ERROR] feature v2 extraction failed: {exc}", file=sys.stderr)
        return 2
    print(f"[INFO] feature v2 output: {args.output_dir} ({config['rows']} sessions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())