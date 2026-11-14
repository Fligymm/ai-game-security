"""Realtime closed-loop aim runner.

The loop connects ScreenGrabber -> AimPipeline -> relative mouse output and is
intended for real-time lab or replay environments where a captured ROI frame is
processed continuously.  Setting ``RealtimeLoopConfig.record_dir`` optionally
writes a multimodal capture session without changing the control path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import time
from typing import Iterator

import cv2
import numpy as np
import supervision as sv

from cv_agent.orchestrator import AimPipeline, AimPipelineResult
from vision.stream.grabber import ScreenGrabber
from vision.stream.safety import GlobalHotkeyKillSwitch
from vision.stream.session_recorder import CaptureMetadata, SessionRecorder
from visualization.aim_debug_overlay import draw_aim_debug_overlay


@dataclass(frozen=True, slots=True)
class RealtimeLoopConfig:
    """Runtime options for the closed-loop runner."""

    algorithm: str | None = None
    apply_mouse: bool = False
    delay_s: float | None = None
    prefer_head: bool | None = None
    hotkeys_enabled: bool = True
    debug_overlay: bool = True
    window_name: str = "RealtimeAimLoop"
    max_mouse_step: float = 24.0
    mouse_deadzone: float = 0.5
    record_dir: str | None = None
    record_fps: int = 60
    record_mode: str = "video"
    record_game: str = "cs2_offline"
    record_scene: str = "unspecified"
    record_operator_id: str = "anonymous"
    record_source: str = "realtime_cs2_agent"
    record_notes: str = ""


class RealtimeAimLoop:
    """Connect screen capture to the aim pipeline in a single running loop."""

    def __init__(
        self,
        grabber: ScreenGrabber | None = None,
        pipeline: AimPipeline | None = None,
        *,
        config: RealtimeLoopConfig | None = None,
        tracker: sv.ByteTrack | None = None,
    ) -> None:
        self.grabber = grabber if grabber is not None else ScreenGrabber()
        self.pipeline = pipeline if pipeline is not None else AimPipeline()
        self.config = config if config is not None else RealtimeLoopConfig()
        self.tracker = tracker if tracker is not None else sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=30,
            minimum_matching_threshold=0.8,
        )
        if pipeline is None:
            self.pipeline = AimPipeline(
                tracker=self.tracker,
                require_external_track_id=True,
            )
        else:
            # Ensure externally supplied pipelines use the loop-owned tracker.
            self.pipeline.tracker = self.tracker
        self.kill_switch = GlobalHotkeyKillSwitch() if self.config.hotkeys_enabled else None
        self._control_warning_emitted = False
        self._frame_index = 0
        if self.config.record_fps <= 0:
            raise ValueError("record_fps must be positive")
        if self.config.record_mode not in {"video", "frames"}:
            raise ValueError("record_mode must be 'video' or 'frames'")
        self.recorder: SessionRecorder | None = None

    def __enter__(self) -> RealtimeAimLoop:
        self.grabber.start()
        if self.kill_switch is not None:
            self.kill_switch.start()
        if self.config.apply_mouse and not self._kill_switch_ready():
            self.stop()
            raise RuntimeError(
                "real mouse control requires an available ESC/F12 kill switch; "
                "use dry-run mode or fix global hotkey registration"
            )
        try:
            self._start_recorder()
        except Exception:
            self.stop()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def _start_recorder(self) -> None:
        if self.recorder is not None or not self.config.record_dir:
            return

        root = Path(self.config.record_dir)
        source = (self.config.record_source or "session").strip() or "session"
        base_id = f"{source}_{time.strftime('%Y%m%d_%H%M%S')}"
        session_id = base_id
        suffix = 1
        while (root / session_id).exists():
            session_id = f"{base_id}_{suffix:02d}"
            suffix += 1

        metadata = CaptureMetadata(
            session_id=session_id,
            source=source,
            game=self.config.record_game,
            scene=self.config.record_scene,
            operator_id=self.config.record_operator_id,
            width=int(self.grabber.roi_width),
            height=int(self.grabber.roi_height),
            target_fps=int(getattr(self.grabber, "target_fps", self.config.record_fps)),
            roi=getattr(self.grabber, "roi_box", None),
            backend=str(getattr(self.grabber, "backend", "unknown") or "unknown"),
            notes=self.config.record_notes,
        )
        recorder = SessionRecorder(
            root,
            metadata,
            video_fps=self.config.record_fps,
            mode=self.config.record_mode,
        )
        try:
            recorder.start()
        except Exception:
            recorder.close()
            raise
        self.recorder = recorder
        print(f"[INFO] Recording multimodal session: {recorder.session_dir}")

    def _stop_recorder(self) -> None:
        if self.recorder is None:
            return
        recorder = self.recorder
        self.recorder = None
        recorder.close()
        print(f"[INFO] Recording closed: {recorder.session_dir}")

    def stop(self) -> None:
        """Stop the capture backend and close any active session recorder."""

        self._stop_recorder()
        if self.kill_switch is not None:
            self.kill_switch.stop()
        self.grabber.stop()

    def step(self, frame: np.ndarray | None = None) -> AimPipelineResult:
        """Run one frame through the loop, capturing if no frame is provided.
        
        CSV logging is ALWAYS performed regardless of apply_mouse state.
        Real control is only sent when apply_mouse=True and kill_switch is not paused.
        """

        if frame is None:
            frame = self.grabber.get_latest_frame()
        capture_timestamp_ns = int(
            getattr(self.grabber, "last_frame_timestamp_ns", 0)
            or time.perf_counter_ns()
        )
        if self.config.record_dir and self.recorder is None:
            self._start_recorder()
        # ✔ MUST: pipeline.run() always receives apply_mouse=False (干运行)
        # Real control decision is handled by controller.apply_correction() vs log_only()
        result = self.pipeline.run(
            frame,
            algorithm=self.config.algorithm,
            apply_mouse=False,  # ✔ 干运行：不在 pipeline 内处理控制
            delay_s=self.config.delay_s,
            prefer_head=self.config.prefer_head,
        )
        if result.selected is None or result.compensated_offset is None:
            self.pipeline.controller.reset()
        else:
            # ALWAYS record offset to CSV (for trajectory analysis)
            active_requested = self.config.apply_mouse and not self._mouse_paused()
            if active_requested and not self._kill_switch_ready():
                active_requested = False
                if not self._control_warning_emitted:
                    print(
                        "[WARNING] real control requested but kill switch is unavailable; "
                        "falling back to CSV-only dry-run"
                    )
                    self._control_warning_emitted = True

            can_apply = bool(getattr(self.pipeline.controller, "can_apply", False))
            if active_requested and can_apply:
                move = self.pipeline.controller.apply_correction(
                    *result.compensated_offset,
                    max_step=self.config.max_mouse_step,
                    deadzone=self.config.mouse_deadzone,
                )
                # Only claim a real input event when the backend can actually
                # emit one and the deadzone did not suppress the movement.
                result = replace(
                    result,
                    applied_mouse=bool(move["sent_dx"] or move["sent_dy"]),
                )
            else:
                # Dry-run, paused, unavailable kill switch, or recording-only
                # backend: log only to CSV (no real control sent).
                self.pipeline.controller.log_only(
                    *result.compensated_offset,
                    max_step=self.config.max_mouse_step,
                    deadzone=self.config.mouse_deadzone,
                )
                if active_requested and not can_apply and not self._control_warning_emitted:
                    print(
                        "[WARNING] real control requested but backend is recording-only; "
                        "falling back to CSV-only dry-run"
                    )
                    self._control_warning_emitted = True
                # Keep applied_mouse=False to indicate no real control was sent

        self._record_step(frame, result, capture_timestamp_ns)
        self._frame_index += 1
        return result

    def _record_step(
        self,
        frame: np.ndarray,
        result: AimPipelineResult,
        capture_timestamp_ns: int,
    ) -> None:
        if self.recorder is None:
            return
        detections = [
            {
                "x1": float(det.x1),
                "y1": float(det.y1),
                "x2": float(det.x2),
                "y2": float(det.y2),
                "confidence": float(det.conf),
                "class_id": int(det.cls_id),
                "track_id": det.track_id,
            }
            for det in result.detections
        ]
        selected = None
        if result.selected is not None:
            target = result.selected
            selected = {
                "x1": float(target.x1),
                "y1": float(target.y1),
                "x2": float(target.x2),
                "y2": float(target.y2),
                "confidence": float(target.conf),
                "class_id": int(target.cls_id),
                "class_name": target.cls_name,
                "track_id": target.track_id,
                "delta_x": float(target.delta_x),
                "delta_y": float(target.delta_y),
            }
        mouse_delta = (
            (float(result.mouse_delta[0]), float(result.mouse_delta[1]))
            if result.mouse_delta is not None
            else None
        )
        trajectory = None
        if result.trajectory is not None:
            trajectory = {
                "name": result.trajectory.name,
                "points": [[float(x), float(y)] for x, y in result.trajectory.points],
            }
        self.recorder.record_frame(
            frame,
            timestamp_ns=capture_timestamp_ns,
            frame_id=self._frame_index,
            detections=detections,
            selected=selected,
            applied_mouse=result.applied_mouse,
            mouse_delta=mouse_delta,
            extra={
                "processed_at_ns": time.perf_counter_ns(),
                "prediction_enabled": bool(result.prediction_enabled),
                "trajectory": trajectory,
            },
        )

    def iterate(self) -> Iterator[AimPipelineResult]:
        """Yield closed-loop results indefinitely until the caller stops it."""

        while True:
            yield self.step()

    def run(self, max_frames: int | None = None, *, preview: bool = False) -> list[AimPipelineResult]:
        """Run the loop for a bounded number of frames or until Esc/q when previewing.
        
        CSV logging is always active regardless of apply_mouse setting.
        Resources are explicitly closed in finally block.
        """

        if self.config.apply_mouse and not self._kill_switch_ready():
            raise RuntimeError(
                "real mouse control requires a running ESC/F12 kill switch; "
                "use the RealtimeAimLoop context manager or dry-run mode"
            )

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
            # Explicit resource cleanup; closes all backends including CSV logger
            try:
                self._stop_recorder()
            except Exception as e:
                print(f"[WARNING] Error closing session recorder: {e}")
            try:
                self.pipeline.controller.close()
            except Exception as e:
                print(f"[WARNING] Error closing controller: {e}")
            
            # Close preview window
            if preview or self.config.debug_overlay:
                try:
                    cv2.destroyWindow(window_name)
                except Exception as e:
                    print(f"[WARNING] Error destroying window: {e}")
        
        return results

    def _kill_switch_ready(self) -> bool:
        return bool(
            self.kill_switch is not None
            and getattr(self.kill_switch, "is_running", False)
            and not self.kill_switch.stopped
        )

    def _mouse_paused(self) -> bool:
        return bool(self.kill_switch is not None and self.kill_switch.paused)

    def _loop_stopped(self) -> bool:
        return bool(self.kill_switch is not None and self.kill_switch.stopped)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from cv_agent.orchestrator import AimPipeline
    from cv_agent.control.factory import create_mouse_backend
    from vision.detection.yolo_detector import YOLODetector
    from vision.stream.grabber import ScreenGrabber

    parser = argparse.ArgumentParser(description="Run the realtime ScreenGrabber -> AimPipeline closed loop")
    parser.add_argument("--algorithm", default=None, help="Trajectory algorithm name")
    parser.add_argument("--apply-mouse", action="store_true", help="Enable real mouse control output (default: dry-run CSV logging only)")
    parser.add_argument("--frames", type=int, default=None, help="Optional frame limit")
    parser.add_argument("--preview", action="store_true", help="Show ROI preview while running")
    parser.add_argument("--no-overlay", action="store_true", help="Disable the debug overlay for capture-only pilot runs")
    parser.add_argument("--no-hotkeys", action="store_true", help="Disable global kill switch hotkeys (dry-run only)")
    parser.add_argument("--weights", default="yolov8n.pt", help="YOLO weights path")
    parser.add_argument("--conf", type=float, default=0.5, help="Detection confidence threshold")
    parser.add_argument("--roi", type=int, default=640, help="Centered square capture size")
    parser.add_argument("--fps", type=int, default=144, help="Requested capture FPS")
    parser.add_argument("--head-only", action="store_true", help="Never fall back to body/other classes")
    parser.add_argument("--max-mouse-step", type=float, default=24.0, help="Maximum mouse pixels sent per frame")
    parser.add_argument("--mouse-deadzone", type=float, default=0.5, help="Stop moving below this pixel error")
    parser.add_argument("--output-confirm-frames", type=int, default=3, help="Frames required before output resumes after a lock change")
    parser.add_argument("--record-dir", default=None, help="Optional multimodal capture root; writes frames/events/manifest")
    parser.add_argument("--record-fps", type=int, default=60, help="Sampling/playback FPS for recorded captures")
    parser.add_argument("--record-mode", choices=("video", "frames"), default="video", help="Capture format: one MP4 or JPEG sequence")
    parser.add_argument("--record-source", default="realtime_cs2_agent", help="Source label, e.g. realtime_cs2_agent or human_cs2")
    parser.add_argument("--record-game", default="cs2_offline", help="Game/scene label stored in session metadata")
    parser.add_argument("--record-scene", default="unspecified", help="Scene label stored in session metadata")
    parser.add_argument("--record-operator-id", default="anonymous", help="Anonymized operator/device id")
    parser.add_argument("--record-notes", default="", help="Free-form notes stored in session metadata")
    parser.add_argument("--backend", choices=("csv", "canvas", "win32", "hid"), default="csv",
                        help="Output backend (csv=dry-run + logging; win32/hid require an injected handler via run_real.py for real output; canvas=visual)")
    parser.add_argument("--backend-output", default=None, help="CSV output path (defaults to timestamped runs/predict file)")
    parser.add_argument("--allow-external-handler", action="store_true", help="Allow externally injected callbacks (required for custom control handlers)")
    args = parser.parse_args()

    # Resolve backend configuration with real control support
    # --apply-mouse explicitly enables control output for win32/hid backends
    # CSV logging is ALWAYS enabled (persisted regardless of control setting)
    apply_mouse_enabled = args.apply_mouse  # Only True if --apply-mouse is explicitly passed
    
    config = RealtimeLoopConfig(
        algorithm=args.algorithm,
        apply_mouse=apply_mouse_enabled,  # Respect user's explicit control choice
        hotkeys_enabled=not args.no_hotkeys,
        debug_overlay=not args.no_overlay,
        max_mouse_step=args.max_mouse_step,
        mouse_deadzone=args.mouse_deadzone,
        record_dir=args.record_dir,
        record_fps=args.record_fps,
        record_mode=args.record_mode,
        record_source=args.record_source,
        record_game=args.record_game,
        record_scene=args.record_scene,
        record_operator_id=args.record_operator_id,
        record_notes=args.record_notes,
    )
    
    grabber = ScreenGrabber(roi_width=args.roi, roi_height=args.roi, target_fps=args.fps)
    detector = YOLODetector(Path(args.weights), conf=args.conf, coord_space="pixel")
    expected_names = {0: "enemy_head", 1: "enemy_body"}
    if detector.class_names != expected_names:
        raise RuntimeError(
            f"Unexpected model class mapping: {detector.class_names}; expected {expected_names}"
        )
    
    # Backend strategy: ALWAYS include CSV for trajectory logging
    # - CSV backend alone: dry-run CSV only
    # - Win32/HID + --apply-mouse: CSV + real control chain
    # - Win32/HID without --apply-mouse: still CSV only (dry-run, trajectory recorded but control disabled)
    backend = create_mouse_backend(
        args.backend,
        output_path=args.backend_output,
        allow_external_handler=args.allow_external_handler,
        always_include_csv=True,  # ALWAYS chain with CSV for complete trajectory logging
    )
    
    pipeline = AimPipeline(
        detector=detector,
        allow_body_fallback=not args.head_only,
        backend=backend,
        output_confirm_frames=args.output_confirm_frames,
    )
    
    try:
        with RealtimeAimLoop(grabber=grabber, pipeline=pipeline, config=config) as loop:
            results = loop.run(max_frames=args.frames, preview=args.preview)
        if results:
            last = results[-1]
            print(f"[INFO] Completed: frames={len(results)} mouse_delta={last.mouse_delta} applied_mouse={last.applied_mouse}")
    finally:
        # Explicit resource cleanup
        try:
            pipeline.controller.close()
        except Exception as e:
            print(f"[WARNING] Error closing controller: {e}")
        try:
            grabber.stop()
        except Exception as e:
            print(f"[WARNING] Error stopping grabber: {e}")
