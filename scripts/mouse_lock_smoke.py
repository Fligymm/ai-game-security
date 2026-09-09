"""Smoke test the short-term mouse lock path and classify trajectory families.

This is intended for offline lab use. By default it only plans and reports a
trajectory. Pass --apply-mouse on Windows to exercise the relative mouse
playback path.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from cv_agent.control.mouse import AimController
from cv_agent.detection.target_state import TargetState
from cv_agent.selection.priority import TargetSelector
from cv_agent.trajectory.catalog import get_trajectory_profile, trajectory_catalog
from cv_agent.trajectory.paths import GENERATORS, smoothness_features


def _print_catalog() -> None:
    print("trajectory catalog:")
    for profile in trajectory_catalog():
        print(
            f"  {profile.name:12s} family={profile.family:15s} "
            f"closed_loop={str(profile.closed_loop):5s} deterministic={str(profile.deterministic):5s} "
            f"tags={','.join(profile.tags) or '-'}"
        )


def _format_summary(summary: dict[str, Any]) -> str:
    parts = []
    for key, value in summary.items():
        if isinstance(value, float):
            parts.append(f"{key}={value:.3f}")
        else:
            parts.append(f"{key}={value}")
    return "  ".join(parts)


def _make_demo_state(x: float, size: float) -> TargetState:
    return TargetState(
        x1=x - size / 2,
        y1=300.0 - size / 2,
        x2=x + size / 2,
        y2=300.0 + size / 2,
        conf=0.9,
        cls_id=0,
        cls_name="enemy_head",
        target_x=x,
        target_y=300.0,
        screen_cx=320.0,
        screen_cy=300.0,
        delta_x=x - 320.0,
        delta_y=0.0,
        frame_w=640,
        frame_h=600,
    )


def _lock_demo_report() -> dict[str, int]:
    selector = TargetSelector()
    for _ in range(8):
        selector.update([_make_demo_state(300.0, 40.0), _make_demo_state(338.0, 39.0)])
    return {
        "lock_switches": selector.state.switch_count,
        "consecutive_lock_frames": selector.state.consecutive_lock_frames,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test mouse lock + trajectory taxonomy")
    parser.add_argument("--algorithm", default="linear", choices=sorted(GENERATORS))
    parser.add_argument("--dx", type=float, default=160.0)
    parser.add_argument("--dy", type=float, default=-80.0)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--alpha", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--delay-s", type=float, default=None)
    parser.add_argument("--apply-mouse", action="store_true", help="Send relative mouse movement")
    parser.add_argument("--lab-modulation", action="store_true", help="Enable tagged offline perturbation data generation")
    parser.add_argument("--noise-scale", type=float, default=0.0)
    parser.add_argument("--overshoot-probability", type=float, default=0.0)
    parser.add_argument("--compare-all", action="store_true", help="Print every registered trajectory")
    parser.add_argument("--list", action="store_true", help="List trajectory catalog and exit")
    parser.add_argument("--out", type=Path, default=None, help="Optional path to save a text summary")
    args = parser.parse_args()

    if args.list:
        _print_catalog()
        return

    controller = AimController()
    names = sorted(GENERATORS) if args.compare_all else [args.algorithm]
    reports: list[str] = []

    for name in names:
        traj = controller.plan(
            args.dx,
            args.dy,
            algorithm=name,
            steps=args.steps,
            alpha=args.alpha,
            seed=args.seed,
            lab_modulation=args.lab_modulation,
            noise_scale=args.noise_scale,
            overshoot_probability=args.overshoot_probability,
            modulation_seed=args.seed,
        )
        profile = get_trajectory_profile(name)
        features = smoothness_features(traj)
        report = {
            "name": traj.name,
            "family": profile.family,
            "deterministic": profile.deterministic,
            "closed_loop": profile.closed_loop,
            "n_points": float(len(traj.points)),
            "n_moves": float(len(traj.deltas)),
            **features,
        }
        line = _format_summary(report)
        print(line)
        print(f"  tags={','.join(profile.tags) or '-'}")
        print(f"  signals={','.join(profile.anticheat_signal)}")
        if name == args.algorithm:
            playback = controller.execute(traj, apply_mouse=args.apply_mouse, delay_s=args.delay_s)
        print(_format_summary({"mouse_applied": float(args.apply_mouse), **playback}))
        print(_format_summary({**_lock_demo_report(), **{
            "lab_modulation": int(traj.extras.get("lab_modulation", 0.0)),
            "overshoot_applied": int(traj.extras.get("overshoot_applied", 0.0)),
        }}))
        reports.append(line)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("\n".join(reports) + "\n", encoding="utf-8")
        print(f"saved summary: {args.out}")


if __name__ == "__main__":
    main()
