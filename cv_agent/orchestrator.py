"""Unified aim pipeline orchestration for frame -> target -> motion execution.

This module keeps the existing components decoupled while providing a single
entry point that will later be easy to feed with real-time screen captures.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cv_agent.control import (
    AimController,
    BaseMouseBackend,
)
from cv_agent.control.factory import create_mouse_backend
from cv_agent.detection.target_state import TargetState, detections_to_states
from cv_agent.prediction.kalman import Kalman2D
from cv_agent.selection.priority import TargetSelector
from cv_agent.trajectory.catalog import TrajectoryProfile, get_trajectory_profile
from cv_agent.trajectory.paths import Trajectory
from vision.detection.detection import Detection
from vision.detection.yolo_detector import YOLODetector


@dataclass(frozen=True)
class AimPipelineResult:
    """Outcome of one end-to-end pipeline pass."""

    frame_shape: tuple[int, ...]
    detections: list[Detection]
    states: list[TargetState]
    selected: TargetState | None
    measurement_offset: tuple[float, float] | None
    filtered_offset: tuple[float, float] | None
    predicted_offset: tuple[float, float] | None
    compensated_offset: tuple[float, float] | None
    mouse_delta: tuple[float, float] | None
    prediction_enabled: bool
    trajectory: Trajectory | None
    trajectory_profile: TrajectoryProfile | None
    features: dict[str, float]
    applied_mouse: bool


class AimPipeline:
    """Run YOLO -> target conversion -> selection -> trajectory -> execution.

    The class is intentionally thin: it wires the existing components together
    without changing their behavior. The only state it owns is the detector,
    controller, and a few defaults for the orchestration step.
    """

    def __init__(
        self,
        detector: YOLODetector | None = None,
        controller: AimController | None = None,
        predictor: Kalman2D | None = None,
        *,
        prefer_head: bool = True,
        default_algorithm: str = "linear",
        prediction_enabled: bool = True,
        prediction_gain: float = 1.0,
        allow_body_fallback: bool = True,
        selector: TargetSelector | None = None,
        backend: BaseMouseBackend | None = None,
        backend_name: str = "csv",
        backend_output: str | Path = "runs/predict/control_moves.csv",
        output_confirm_frames: int = 3,
        tracker: object | None = None,
        require_external_track_id: bool = False,
    ) -> None:
        self.detector = detector if detector is not None else YOLODetector()
        self.tracker = tracker
        self.controller = controller if controller is not None else AimController(
            backend=backend if backend is not None else create_mouse_backend(backend_name, output_path=backend_output)
        )
        self.predictor = predictor if predictor is not None else Kalman2D()
        self.prefer_head = bool(prefer_head)
        self.default_algorithm = default_algorithm
        self.prediction_enabled = bool(prediction_enabled)
        self.prediction_gain = float(prediction_gain)
        self.allow_body_fallback = bool(allow_body_fallback)
        self.selector = selector if selector is not None else TargetSelector()
        if require_external_track_id and selector is None:
            from cv_agent.selection.priority import TargetSelectionConfig

            self.selector = TargetSelector(TargetSelectionConfig(require_external_track_id=True))
        if output_confirm_frames < 1:
            raise ValueError("output_confirm_frames must be >= 1")
        self.output_confirm_frames = int(output_confirm_frames)
        self._output_track_id: int | None = None
        self._output_track_streak = 0
        self._last_selected_cls_id: int | None = None
        if not 0.0 <= self.prediction_gain <= 1.0:
            raise ValueError("prediction_gain must be in [0, 1]")

    def reset_prediction(self) -> None:
        """Reset the Kalman state for a new target or a new capture session."""

        self.predictor = Kalman2D()
        self._last_selected_cls_id = None
        self.selector.reset()
        self._output_track_id = None
        self._output_track_streak = 0

    def __call__(
        self,
        frame: np.ndarray,
        *,
        algorithm: str | None = None,
        apply_mouse: bool = False,
        delay_s: float | None = None,
        prefer_head: bool | None = None,
        trajectory_kwargs: dict[str, object] | None = None,
    ) -> AimPipelineResult:
        return self.run(
            frame,
            algorithm=algorithm,
            apply_mouse=apply_mouse,
            delay_s=delay_s,
            prefer_head=prefer_head,
            trajectory_kwargs=trajectory_kwargs,
        )

    def run(
        self,
        frame: np.ndarray,
        *,
        algorithm: str | None = None,
        apply_mouse: bool = False,
        delay_s: float | None = None,
        prefer_head: bool | None = None,
        trajectory_kwargs: dict[str, object] | None = None,
    ) -> AimPipelineResult:
        """Execute one full pass on a single OpenCV BGR frame."""

        chosen_algorithm = algorithm or self.default_algorithm
        selected_preference = self.prefer_head if prefer_head is None else bool(prefer_head)
        plan_kwargs = dict(trajectory_kwargs or {})

        detections = self.detector.detect_frame(frame)
        detections = self._update_tracker(detections)
        states = detections_to_states(detections, frame.shape, self.detector.class_names)
        selected = self.selector.update(
            states,
            prefer_head=selected_preference,
            allow_body_fallback=self.allow_body_fallback,
        )
        output_allowed = self._output_gate(selected)

        # Never blend measurements from different semantic targets. A body
        # measurement followed by a head measurement would otherwise leave
        # the Kalman state near the torso and pull the trajectory off target.
        if selected is None:
            # A missing active target must produce no movement, but the
            # selector's lock timeout must continue across frames.
            self.predictor = Kalman2D()
            self._last_selected_cls_id = None
        elif self._last_selected_cls_id != selected.cls_id:
            self.reset_prediction()
            self._last_selected_cls_id = selected.cls_id

        measurement_offset: tuple[float, float] | None = None
        filtered_offset: tuple[float, float] | None = None
        predicted_offset: tuple[float, float] | None = None
        compensated_offset: tuple[float, float] | None = None
        trajectory = None
        trajectory_profile = None
        features: dict[str, float] = {}
        if selected is not None and output_allowed:
            measurement_offset = selected.offset
            if self.prediction_enabled:
                filtered_offset = self.predictor.predict_then_update(*measurement_offset)
                # Advance once more to obtain the next-frame lead estimate.
                predicted_offset = self.predictor.predict()
                compensated_offset = _blend_offsets(
                    filtered_offset,
                    predicted_offset,
                    self.prediction_gain,
                )
            else:
                filtered_offset = measurement_offset
                predicted_offset = measurement_offset
                compensated_offset = measurement_offset

            plan_dx, plan_dy = compensated_offset
            trajectory = self.controller.plan(
                plan_dx,
                plan_dy,
                algorithm=chosen_algorithm,
                **plan_kwargs,
            )
            trajectory_profile = get_trajectory_profile(trajectory.name)
            features = self.controller.execute(
                trajectory,
                apply_mouse=apply_mouse,
                delay_s=delay_s,
            )

        return AimPipelineResult(
            frame_shape=tuple(int(v) for v in frame.shape),
            detections=detections,
            states=states,
            selected=selected,
            measurement_offset=measurement_offset,
            filtered_offset=filtered_offset,
            predicted_offset=predicted_offset,
            compensated_offset=compensated_offset,
            mouse_delta=compensated_offset,
            prediction_enabled=self.prediction_enabled,
            trajectory=trajectory,
            trajectory_profile=trajectory_profile,
            features=features,
            applied_mouse=bool(apply_mouse and trajectory is not None),
        )

    def _update_tracker(self, detections: list[Detection]) -> list[Detection]:
        if self.tracker is None:
            return detections
        import supervision as sv

        if detections:
            tracked_input = sv.Detections(
                xyxy=np.asarray([item.bbox for item in detections], dtype=np.float32),
                confidence=np.asarray([item.conf for item in detections], dtype=np.float32),
                class_id=np.asarray([item.cls_id for item in detections], dtype=np.int32),
            )
        else:
            tracked_input = sv.Detections(
                xyxy=np.empty((0, 4), dtype=np.float32),
                confidence=np.empty((0,), dtype=np.float32),
                class_id=np.empty((0,), dtype=np.int32),
            )
        tracked = self.tracker.update_with_detections(tracked_input)
        ids = tracked.tracker_id
        if ids is None:
            return []
        output: list[Detection] = []
        for index, track_id in enumerate(ids):
            if track_id is None:
                continue
            output.append(
                Detection(
                    float(tracked.xyxy[index, 0]),
                    float(tracked.xyxy[index, 1]),
                    float(tracked.xyxy[index, 2]),
                    float(tracked.xyxy[index, 3]),
                    float(tracked.confidence[index]),
                    int(tracked.class_id[index]),
                    int(track_id),
                )
            )
        return output

    def _output_gate(self, selected: TargetState | None) -> bool:
        """Require a stable lock ID before any movement reaches a backend."""
        if selected is None or selected.track_id is None:
            self._output_track_id = None
            self._output_track_streak = 0
            self.controller.reset()
            return False
        if selected.track_id != self._output_track_id:
            self._output_track_id = selected.track_id
            self._output_track_streak = 1
            self.controller.reset()
            return self.output_confirm_frames == 1
        self._output_track_streak += 1
        return self._output_track_streak >= self.output_confirm_frames


def _blend_offsets(
    filtered_offset: tuple[float, float],
    predicted_offset: tuple[float, float],
    prediction_gain: float,
) -> tuple[float, float]:
    """Blend Kalman filtered and predicted offsets for motion compensation."""

    gain = float(prediction_gain)
    fx, fy = filtered_offset
    px, py = predicted_offset
    return fx + gain * (px - fx), fy + gain * (py - fy)
