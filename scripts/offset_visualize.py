"""Phase-1 demo: YOLODetector boxes → ΔX/ΔY overlay + trajectory algorithms.

Uses vision.detection.YOLODetector only. Does not change class ids
(0=enemy_head, 1=enemy_body). Mouse playback is off unless --apply-mouse.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from cv_agent.control.mouse import AimController
from cv_agent.detection.target_state import detections_to_states
from cv_agent.prediction.kalman import Kalman2D
from cv_agent.selection.priority import select_target
from cv_agent.trajectory.catalog import get_trajectory_profile
from cv_agent.trajectory.paths import GENERATORS, generate, smoothness_features
from vision.detection.yolo_detector import YOLODetector
from visualization.offset_overlay import draw_offset_overlay


def _default_image() -> Path:
    val = _REPO / "datasets" / "cs2_custom" / "val" / "images"
    for path in sorted(val.glob("*.png")) + sorted(val.glob("*.jpg")):
        if path.name != ".gitkeep":
            return path
    return val / "test.jpg"


def main() -> None:
    parser = argparse.ArgumentParser(description="Offset visualization + trajectory lab")
    parser.add_argument("--weights", default=str(_REPO / "runs" / "detect" / "cs2_detection_v1" / "weights" / "best.pt"))
    parser.add_argument("--image", default=str(_default_image()))
    parser.add_argument("--conf", type=float, default=0.5)
    parser.add_argument("--algorithm", default="bezier", choices=sorted(GENERATORS))
    parser.add_argument("--compare-all", action="store_true")
    parser.add_argument("--apply-mouse", action="store_true", help="Play relative mouse (offline lab only)")
    parser.add_argument(
        "--out",
        default=str(_REPO / "runs" / "predict" / "offset_analysis" / "output_analysis.jpg"),
    )
    args = parser.parse_args()

    frame = cv2.imread(args.image)
    if frame is None:
        raise FileNotFoundError(f"cannot read image: {args.image}")

    detector = YOLODetector(args.weights, conf=args.conf, coord_space="pixel", device=0)
    detections = detector.detect_frame(frame)
    states = detections_to_states(detections, frame.shape, detector.class_names)
    selected = select_target(states)

    kf = Kalman2D()
    if selected is not None:
        filt_x, filt_y = kf.predict_then_update(selected.delta_x, selected.delta_y)
        pred_x, pred_y = kf.predict()
        print(
            f"selected [{selected.cls_name}] conf={selected.conf:.3f}  "
            f"ΔX={selected.delta_x:.1f}px  ΔY={selected.delta_y:.1f}px"
        )
        print(f"kalman filtered  ΔX={filt_x:.1f}  ΔY={filt_y:.1f}")
        print(f"kalman next-step ΔX={pred_x:.1f}  ΔY={pred_y:.1f}")
        names = [args.algorithm] if not args.compare_all else list(GENERATORS)
        controller = AimController()
        chosen = None
        for name in names:
            traj = generate(name, selected.delta_x, selected.delta_y, seed=42)
            profile = get_trajectory_profile(name)
            feat = smoothness_features(traj)
            print(
                f"  traj={traj.name:12s}  family={profile.family:15s}  "
                f"steps={int(feat['n_steps']):3d}  path={feat['path_len']:.1f}  "
                f"straight={feat['straightness']:.3f}  jerk={feat['jerk_mean']:.3f}"
            )
            print(
                f"    tags={','.join(profile.tags) or '-'}  "
                f"signals={','.join(profile.anticheat_signal)}"
            )
            if name == args.algorithm:
                chosen = traj
                controller.execute(traj, apply_mouse=args.apply_mouse)
        overlay = draw_offset_overlay(frame, states, selected, chosen)
    else:
        print("no detections")
        overlay = draw_offset_overlay(frame, states)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), overlay)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
