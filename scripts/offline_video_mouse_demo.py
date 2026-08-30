"""Play an offline clip while visualizing and optionally applying aim motion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cv_agent.orchestrator import AimPipeline
from vision.detection.yolo_detector import YOLODetector
from visualization.aim_debug_overlay import draw_aim_debug_overlay


def main() -> None:
    parser = argparse.ArgumentParser(description="Visual offline video -> aim -> mouse demo")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--conf", type=float, default=0.5)
    parser.add_argument("--delay-s", type=float, default=0.01)
    parser.add_argument("--apply-mouse", action="store_true")
    parser.add_argument("--save", type=Path, default=None, help="Optional rendered output video")
    args = parser.parse_args()

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {args.video}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    writer = None
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(args.save), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )
        if not writer.isOpened():
            raise RuntimeError(f"Unable to open output video: {args.save}")

    pipeline = AimPipeline(
        detector=YOLODetector(args.weights, conf=args.conf, coord_space="pixel")
    )
    frames = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            result = pipeline.run(
                frame,
                apply_mouse=args.apply_mouse,
                delay_s=args.delay_s,
            )
            overlay = draw_aim_debug_overlay(frame, result)
            cv2.putText(
                overlay,
                f"frame={frames}  mouse_output={args.apply_mouse}  press q/ESC to stop",
                (12, overlay.shape[0] - 14),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            if writer is not None:
                writer.write(overlay)
            cv2.imshow("Offline Aim + Mouse Demo", overlay)
            key = cv2.waitKey(max(1, int(round(1000.0 / max(fps, 1.0))))) & 0xFF
            frames += 1
            if key in (ord("q"), 27):
                break
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()

    print(f"completed frames={frames} mouse_output={args.apply_mouse}")
    if args.save:
        print(f"rendered_video={args.save}")


if __name__ == "__main__":
    main()
