"""Run the existing CV Agent pipeline over a captured P0-B video, dry-run only.

The source video is never modified. This tool:
- validates the source H/B POV session;
- reads frames with OpenCV;
- reuses YOLODetector -> AimPipeline -> CSV logging;
- forces apply_mouse=False;
- writes per-frame inference JSONL plus source/model hashes.

It does not start the game, send input, or call run_real.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cv_agent.control.backends.csv_logger import CSVLoggerBackend
from cv_agent.orchestrator import AimPipeline
from tools.check_fps_pilot import check_pilot
from vision.detection.tiled_detector import TiledDetector
from vision.detection.yolo_detector import YOLODetector

import supervision as sv


# Pre-finetune model is the safer default for POV/head analysis as of 2026-11-16;
# pass --model explicitly to use the fine-tuned candidate.
DEFAULT_MODEL = _REPO_ROOT / "runs" / "detect" / "cs2_detection_v2" / "weights" / "best.onnx"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_inference_meta(
    *,
    source_session_dir: Path,
    source_session: dict[str, Any],
    source_video: Path,
    source_video_sha256: str,
    model_path: Path,
    model_sha256: str | None,
    config: dict[str, Any],
    output_files: list[Path],
) -> dict[str, Any]:
    """Build the machine-readable source/model association record."""

    return {
        "schema_version": "anticheat.cv_offline_inference.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": True,
        "real_control": False,
        "apply_mouse": False,
        "source_session_id": source_session.get("session_id"),
        "source_session_dir": str(source_session_dir),
        "source_agent_type": source_session.get("extra", {}).get("agent_type"),
        "source_capture_source": source_session.get("extra", {}).get("capture_source"),
        "source_view_mode": source_session.get("extra", {}).get("view_mode"),
        "source_protocol_version": source_session.get("extra", {}).get("protocol_version"),
        "source_video": str(source_video),
        "source_video_sha256": source_video_sha256,
        "model": str(model_path),
        "model_sha256": model_sha256,
        "config": config,
        "outputs": [str(path) for path in output_files],
    }


def _load_capture_timestamps(session_dir: Path) -> list[int]:
    """Read per-record capture timestamps from events.jsonl, if available."""

    path = session_dir / "events.jsonl"
    if not path.is_file():
        return []
    rows: dict[int, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        index = event.get("record_index")
        timestamp = event.get("timestamp_ns")
        if isinstance(index, int) and isinstance(timestamp, int):
            rows[index] = timestamp
    return [rows[i] for i in sorted(rows)]


def _detection_payload(det: Any) -> dict[str, Any]:
    return {
        "x1": float(det.x1),
        "y1": float(det.y1),
        "x2": float(det.x2),
        "y2": float(det.y2),
        "confidence": float(det.conf),
        "class_id": int(det.cls_id),
        "track_id": getattr(det, "track_id", None),
    }


def _selected_payload(selected: Any) -> dict[str, Any] | None:
    if selected is None:
        return None
    return {
        "x1": float(selected.x1),
        "y1": float(selected.y1),
        "x2": float(selected.x2),
        "y2": float(selected.y2),
        "confidence": float(selected.conf),
        "class_id": int(selected.cls_id),
        "class_name": selected.cls_name,
        "track_id": selected.track_id,
        "delta_x": float(selected.delta_x),
        "delta_y": float(selected.delta_y),
    }


def _trajectory_payload(trajectory: Any) -> dict[str, Any] | None:
    if trajectory is None:
        return None
    return {
        "name": trajectory.name,
        "points": [[float(x), float(y)] for x, y in trajectory.points],
    }


def run_offline(
    source_session_dir: str | Path,
    output_dir: str | Path,
    *,
    model_path: str | Path = DEFAULT_MODEL,
    conf: float = 0.35,
    iou: float = 0.5,
    max_frames: int | None = None,
    require_verified_source: bool = True,
    tile_size: int = 720,
    grid: int = 3,
) -> Path:
    """Run dry-run inference and return the output directory."""

    source_dir = Path(source_session_dir)
    source_check = check_pilot(source_dir, verify_hash=True)
    if require_verified_source and not source_check.get("ok"):
        raise RuntimeError(
            "source session is not verified: "
            + json.dumps(source_check.get("errors", []), ensure_ascii=False)
        )

    source_video = source_dir / "capture.mp4"
    if not source_video.is_file():
        raise FileNotFoundError(f"source video missing: {source_video}")
    session = json.loads((source_dir / "session.json").read_text(encoding="utf-8"))
    event_timestamps = _load_capture_timestamps(source_dir)
    first_capture_ns = event_timestamps[0] if event_timestamps else None

    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    model = Path(model_path)
    if not model.is_file():
        raise FileNotFoundError(f"model missing: {model}")

    capture = cv2.VideoCapture(str(source_video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot decode source video: {source_video}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        base_detector = YOLODetector(model, conf=conf, iou=iou, coord_space="pixel")
        expected_names = {0: "enemy_head", 1: "enemy_body"}
        if base_detector.class_names != expected_names:
            raise RuntimeError(
                f"unexpected model class mapping: {base_detector.class_names}; expected {expected_names}"
            )
        detector = TiledDetector(
            base_detector,
            tile_size=tile_size,
            grid=grid,
            nms_iou=iou,
        )
        backend = CSVLoggerBackend(output / "control_moves.csv")
        pipeline = AimPipeline(
            detector=detector,
            backend=backend,
            tracker=sv.ByteTrack(),
            require_external_track_id=True,
            output_confirm_frames=1,
        )
        csv_path = output / "control_moves.csv"
        jsonl_path = output / "inference_frames.jsonl"
        try:
            with jsonl_path.open("w", encoding="utf-8", buffering=1) as handle:
                frame_index = 0
                while max_frames is None or frame_index < max_frames:
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        break
                    video_time_s = frame_index / fps if fps > 0 else None
                    capture_time_s = (
                        (event_timestamps[frame_index] - first_capture_ns) / 1_000_000_000.0
                        if (
                            first_capture_ns is not None
                            and frame_index < len(event_timestamps)
                        )
                        else None
                    )
                    pipeline.controller.set_output_context(
                        {
                            "source_session_id": session.get("session_id"),
                            "frame_index": frame_index,
                            "video_time_s": video_time_s,
                            "capture_time_s": capture_time_s,
                            "dry_run": True,
                        }
                    )
                    result = pipeline.run(frame, apply_mouse=False)
                    # AimPipeline.execute() intentionally does no output when
                    # apply_mouse=False; log the planned correction explicitly
                    # so the offline CSV remains a complete dry-run record.
                    # Re-set context after run(): execute() sets trajectory extras,
                    # which would otherwise drop the source/frame association.
                    pipeline.controller.set_output_context(
                        {
                            "source_session_id": session.get("session_id"),
                            "frame_index": frame_index,
                            "video_time_s": video_time_s,
                            "capture_time_s": capture_time_s,
                            "dry_run": True,
                        }
                    )
                    if result.selected is not None and result.compensated_offset is not None:
                        pipeline.controller.log_only(*result.compensated_offset)
                    record = {
                        "schema_version": "anticheat.cv_offline_inference.v1",
                        "dry_run": True,
                        "real_control": False,
                        "source_session_id": session.get("session_id"),
                        "frame_index": frame_index,
                        "video_time_s": video_time_s,
                        "capture_time_s": capture_time_s,
                        "detections": [_detection_payload(det) for det in result.detections],
                        "selected": _selected_payload(result.selected),
                        "compensated_offset": list(result.compensated_offset) if result.compensated_offset else None,
                        "mouse_delta": list(result.mouse_delta) if result.mouse_delta else None,
                        "applied_mouse": False,
                        "trajectory": _trajectory_payload(result.trajectory),
                        "features": result.features,
                    }
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    frame_index += 1
        finally:
            try:
                pipeline.controller.close()
            except Exception:
                pass

        source_sha = _sha256(source_video)
        model_sha = _sha256(model)
        meta_path = output / "inference_meta.json"
        meta = build_inference_meta(
            source_session_dir=source_dir,
            source_session=session,
            source_video=source_video,
            source_video_sha256=source_sha,
            model_path=model,
            model_sha256=model_sha,
            config={
                "conf": conf,
                "iou": iou,
                "tile_size": tile_size,
                "grid": grid,
                "max_frames": max_frames,
                "video_fps": fps,
                "video_frame_count": frame_count,
                "video_width": width,
                "video_height": height,
                "dry_run": True,
                "real_control": False,
                "apply_mouse": False,
                "capture_time_source": "events.jsonl/timestamp_ns",
                "capture_event_rows": len(event_timestamps),
            },
            output_files=[jsonl_path, csv_path],
        )
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest_path = output / "inference_manifest.json"
        manifest = {
            "schema_version": "anticheat.cv_offline_inference_manifest.v1",
            "source_session_id": session.get("session_id"),
            "source_video_sha256": source_sha,
            "model_sha256": model_sha,
            "files": [
                {"path": path.name, "size": path.stat().st_size, "sha256": _sha256(path)}
                for path in (jsonl_path, csv_path, meta_path)
            ],
            "dry_run": True,
            "real_control": False,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return output
    finally:
        capture.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run CV Agent over a captured H/B POV video")
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--frames", type=int, default=None)
    parser.add_argument("--tile-size", type=int, default=720)
    parser.add_argument("--grid", type=int, default=3)
    parser.add_argument("--allow-unverified-source", action="store_true")
    args = parser.parse_args(argv)
    try:
        output = run_offline(
            args.session_dir,
            args.output_dir,
            model_path=args.model,
            conf=args.conf,
            iou=args.iou,
            max_frames=args.frames,
            require_verified_source=not args.allow_unverified_source,
            tile_size=args.tile_size,
            grid=args.grid,
        )
    except Exception as exc:
        print(f"[ERROR] offline inference failed: {exc}", file=sys.stderr)
        return 2
    print(f"[INFO] dry-run inference written to: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())