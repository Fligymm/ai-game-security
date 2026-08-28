"""Unified aim pipeline orchestration for frame -> target -> motion execution.

This module keeps the existing components decoupled while providing a single
entry point that will later be easy to feed with real-time screen captures.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cv_agent.control.mouse import AimController
from cv_agent.detection.target_state import TargetState, detections_to_states
from cv_agent.prediction.kalman import Kalman2D
from cv_agent.selection.priority import select_target
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
    ) -> None:
        self.detector = detector if detector is not None else YOLODetector()
        self.controller = controller if controller is not None else AimController()
        self.predictor = predictor if predictor is not None else Kalman2D()
        self.prefer_head = bool(prefer_head)
        self.default_algorithm = default_algorithm
        self.prediction_enabled = bool(prediction_enabled)
        self.prediction_gain = float(prediction_gain)
        if not 0.0 <= self.prediction_gain <= 1.0:
            raise ValueError("prediction_gain must be in [0, 1]")

    def reset_prediction(self) -> None:
        """Reset the Kalman state for a new target or a new capture session."""

        self.predictor = Kalman2D()

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
        states = detections_to_states(detections, frame.shape, self.detector.class_names)
        selected = select_target(states, prefer_head=selected_preference)

        measurement_offset: tuple[float, float] | None = None
        filtered_offset: tuple[float, float] | None = None
        predicted_offset: tuple[float, float] | None = None
        compensated_offset: tuple[float, float] | None = None
        trajectory = None
        trajectory_profile = None
        features: dict[str, float] = {}
        if selected is not None:
            measurement_offset = selected.offset
            if self.prediction_enabled:
                filtered_offset = self.predictor.predict_then_update(*measurement_offset)
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