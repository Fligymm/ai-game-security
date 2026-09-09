"""Offline benchmark for control-output backends.

CSV and Canvas are simulation sinks. The script never calls a platform input
API. ``--backend hid`` is intentionally rejected by the protocol-only backend
until a separately reviewed transport is supplied.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cv_agent.orchestrator import AimPipeline, create_mouse_backend
from cv_agent.trajectory.paths import apply_lab_perturbation, smoothness_features
from vision.detection.yolo_detector import YOLODetector


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline control backend benchmark")
    parser.add_argument("--video", type=Path, default=ROOT / "test_video.mp4")
    parser.add_argument("--weights", type=Path, default=ROOT / "runs" / "detect" / "cs2_detection_v2" / "weights" / "best.pt")
    parser.add_argument("--backend", choices=("csv", "canvas", "hid"), default="csv")
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "benchmarks" / "control_moves.csv")
    parser.add_argument("--algorithm", default="bezier")
    parser.add_argument("--conf", type=float, default=0.5)
    parser.add_argument("--max-frames", type=int, default=300)
    parser.add_argument("--noise-scale", type=float, default=0.6)
    parser.add_argument("--overshoot-probability", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--preview-video", action="store_true")
    args = parser.parse_args()

    if not args.video.exists():
        raise FileNotFoundError(f"video not found: {args.video}")
    if not args.weights.exists():
        raise FileNotFoundError(f"weights not found: {args.weights}")

    backend = create_mouse_backend(args.backend, output_path=args.output)
    pipeline = AimPipeline(
        detector=YOLODetector(args.weights, conf=args.conf, coord_space="pixel"),
        backend=backend,
        default_algorithm=args.algorithm,
    )
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise RuntimeError(f"unable to open video: {args.video}")

    frames = 0
    selected = 0
    jerk_values: list[float] = []
    path_values: list[float] = []
    start = time.perf_counter()
    try:
        while frames < args.max_frames:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            result = pipeline.run(
                frame,
                apply_mouse=True,
                trajectory_kwargs={
                    "lab_modulation": True,
                    "noise_scale": args.noise_scale,
                    "overshoot_probability": args.overshoot_probability,
                    "modulation_seed": args.seed + frames,
                },
            )
            if result.selected is not None:
                selected += 1
            if result.trajectory is not None:
                # Re-apply through the public helper for callers comparing APIs.
                modulated = apply_lab_perturbation(result.trajectory, noise_scale=0.0, seed=args.seed + frames)
                features = smoothness_features(modulated)
                jerk_values.append(features.get("jerk_mean", 0.0))
                path_values.append(features.get("path_len", 0.0))
            if args.preview_video:
                cv2.imshow("Offline Control Benchmark", frame)
                if cv2.waitKey(1) & 0xFF in (27, ord("q")):
                    break
            frames += 1
    finally:
        cap.release()
        cv2.destroyAllWindows()
        pipeline.controller.close()

    elapsed = time.perf_counter() - start
    print(
        f"backend={args.backend} frames={frames} selected_frames={selected} "
        f"elapsed_s={elapsed:.3f} fps={frames / max(elapsed, 1e-9):.2f} "
        f"target_switches={pipeline.selector.state.switch_count} "
        f"locked_frames={pipeline.selector.state.consecutive_lock_frames} "
        f"jerk_mean={np.mean(jerk_values) if jerk_values else 0.0:.4f} "
        f"path_mean={np.mean(path_values) if path_values else 0.0:.4f}"
    )
    if args.backend == "csv":
        print(f"csv_output={args.output}")


if __name__ == "__main__":
    main()
