"""Realtime closed-loop aim runner.

The loop connects ScreenGrabber -> AimPipeline -> relative mouse output and is
intended for real-time lab or replay environments where a captured ROI frame is
processed continuously.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterator

import cv2
import numpy as np

from cv_agent.orchestrator import AimPipeline, AimPipelineResult
from vision.stream.grabber import ScreenGrabber
from vision.stream.safety import GlobalHotkeyKillSwitch
from visualization.aim_debug_overlay import draw_aim_debug_overlay


@dataclass(frozen=True, slots=True)
class RealtimeLoopConfig:
    """Runtime options for the closed-loop runner."""

    algorithm: str | None = None
    apply_mouse: bool = True
    delay_s: float | None = None
    prefer_head: bool | None = None
    hotkeys_enabled: bool = True
    debug_overlay: bool = True
    window_name: str = "RealtimeAimLoop"
    max_mouse_step: float = 24.0
    mouse_deadzone: float = 0.5


class RealtimeAimLoop:
    """Connect screen capture to the aim pipeline in a single running loop."""

    def __init__(
        self,
        grabber: ScreenGrabber | None = None,
        pipeline: AimPipeline | None = None,
        *,
        config: RealtimeLoopConfig | None = None,
    ) -> None:
        self.grabber = grabber if grabber is not None else ScreenGrabber()
        self.pipeline = pipeline if pipeline is not None else AimPipeline()
        self.config = config if config is not None else RealtimeLoopConfig()
        self.kill_switch = GlobalHotkeyKillSwitch() if self.config.hotkeys_enabled else None

    def __enter__(self) -> RealtimeAimLoop:
        self.grabber.start()
        if self.kill_switch is not None:
            self.kill_switch.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def stop(self) -> None:
        """Stop the capture backend."""

        if self.kill_switch is not None:
            self.kill_switch.stop()
        self.grabber.stop()

    def step(self, frame: np.ndarray | None = None) -> AimPipelineResult:
        """Run one frame through the loop, capturing if no frame is provided."""

        if frame is None:
            frame = self.grabber.get_latest_frame()
        result = self.pipeline.run(
            frame,
            algorithm=self.config.algorithm,
            apply_mouse=False,
            delay_s=self.config.delay_s,
            prefer_head=self.config.prefer_head,
        )
        if result.selected is None or result.compensated_offset is None:
            self.pipeline.controller.reset()
            self.pipeline.reset_prediction()
        elif self.config.apply_mouse and not self._mouse_paused():
            self.pipeline.controller.apply_correction(
                *result.compensated_offset,
                max_step=self.config.max_mouse_step,
                deadzone=self.config.mouse_deadzone,
            )
            result = replace(result, applied_mouse=True)
        return result

    def iterate(self) -> Iterator[AimPipelineResult]:
        """Yield closed-loop results indefinitely until the caller stops it."""

        while True:
            yield self.step()

    def run(self, max_frames: int | None = None, *, preview: bool = False) -> list[AimPipelineResult]:
        """Run the loop for a bounded number of frames or until Esc/q when previewing."""

        results: list[AimPipelineResult] = []
        window_name = self.config.window_name
        if preview or self.config.debug_overlay:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, self.grabber.roi_width, self.grabber.roi_height)

        try:
            frame_idx = 0
            while max_frames is None or frame_idx < max_frames:
                if self._loop_stopped():
                    break
                frame = self.grabber.get_latest_frame()
                result = self.step(frame)
                results.append(result)
                if preview or self.config.debug_overlay:
                    overlay = draw_aim_debug_overlay(
                        frame,
                        result,
                        paused=self._mouse_paused(),
                        kill_switch_active=self.kill_switch is not None and self.kill_switch.available,
                    )
                    cv2.imshow(window_name, overlay)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        break
                frame_idx += 1
        finally:
            if preview or self.config.debug_overlay:
                cv2.destroyWindow(window_name)
        return results

    def _mouse_paused(self) -> bool:
        return bool(self.kill_switch is not None and self.kill_switch.paused)

    def _loop_stopped(self) -> bool:
        return bool(self.kill_switch is not None and self.kill_switch.stopped)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from cv_agent.orchestrator import AimPipeline
    from vision.detection.yolo_detector import YOLODetector
    from vision.stream.grabber import ScreenGrabber

    parser = argparse.ArgumentParser(description="Run the realtime ScreenGrabber -> AimPipeline closed loop")
    parser.add_argument("--algorithm", default=None, help="Trajectory algorithm name")
    parser.add_argument("--no-mouse", action="store_true", help="Plan without applying mouse movement")
    parser.add_argument("--frames", type=int, default=None, help="Optional frame limit")
    parser.add_argument("--preview", action="store_true", help="Show ROI preview while running")
    parser.add_argument("--no-hotkeys", action="store_true", help="Disable global kill switch hotkeys")
    parser.add_argument("--weights", default="yolov8n.pt", help="YOLO weights path")
    parser.add_argument("--conf", type=float, default=0.5, help="Detection confidence threshold")
    parser.add_argument("--roi", type=int, default=640, help="Centered square capture size")
    parser.add_argument("--fps", type=int, default=144, help="Requested capture FPS")
    parser.add_argument("--head-only", action="store_true", help="Never fall back to body/other classes")
    parser.add_argument("--max-mouse-step", type=float, default=24.0, help="Maximum mouse pixels sent per frame")
    parser.add_argument("--mouse-deadzone", type=float, default=0.5, help="Stop moving below this pixel error")
    args = parser.parse_args()

    config = RealtimeLoopConfig(
        algorithm=args.algorithm,
        apply_mouse=not args.no_mouse,
        hotkeys_enabled=not args.no_hotkeys,
        max_mouse_step=args.max_mouse_step,
        mouse_deadzone=args.mouse_deadzone,
    )
    grabber = ScreenGrabber(roi_width=args.roi, roi_height=args.roi, target_fps=args.fps)
    detector = YOLODetector(Path(args.weights), conf=args.conf, coord_space="pixel")
    expected_names = {0: "enemy_head", 1: "enemy_body"}
    if detector.class_names != expected_names:
        raise RuntimeError(
            f"Unexpected model class mapping: {detector.class_names}; expected {expected_names}"
        )
    pipeline = AimPipeline(
        detector=detector,
        allow_body_fallback=not args.head_only,
    )
    with RealtimeAimLoop(grabber=grabber, pipeline=pipeline, config=config) as loop:
        results = loop.run(max_frames=args.frames, preview=args.preview)
    if results:
        last = results[-1]
        print(f"frames={len(results)} mouse_delta={last.mouse_delta} applied_mouse={last.applied_mouse}")
