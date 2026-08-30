"""Rich debug overlay for the realtime aim loop."""

from __future__ import annotations

import cv2
import numpy as np

from cv_agent.detection.target_state import BODY_CLS, HEAD_CLS, TargetState
from cv_agent.orchestrator import AimPipelineResult


def draw_aim_debug_overlay(
    frame: np.ndarray,
    result: AimPipelineResult,
    *,
    paused: bool = False,
    kill_switch_active: bool = False,
) -> np.ndarray:
    """Draw detections, lock target, prediction, crosshair, and motion vector."""

    canvas = frame.copy()
    height, width = canvas.shape[:2]
    center = (width // 2, height // 2)

    _draw_crosshair(canvas, center)
    _draw_status(canvas, result, paused=paused, kill_switch_active=kill_switch_active)
    _draw_detections(canvas, result.states, result.selected, center)
    _draw_prediction(canvas, result.predicted_offset, center)
    _draw_motion_vector(canvas, result.mouse_delta or result.compensated_offset, center, result)
    _draw_target_marker(canvas, result.selected, center)
    return canvas


def _draw_crosshair(canvas: np.ndarray, center: tuple[int, int]) -> None:
    cx, cy = center
    cv2.line(canvas, (cx - 18, cy), (cx + 18, cy), (255, 255, 255), 1, cv2.LINE_AA)
    cv2.line(canvas, (cx, cy - 18), (cx, cy + 18), (255, 255, 255), 1, cv2.LINE_AA)
    cv2.circle(canvas, center, 3, (255, 255, 255), -1)


def _draw_status(
    canvas: np.ndarray,
    result: AimPipelineResult,
    *,
    paused: bool,
    kill_switch_active: bool,
) -> None:
    lines = [
        f"pred={result.prediction_enabled} applied_mouse={result.applied_mouse}",
        f"selected={_selected_label(result.selected)} target={_fmt_point(result.selected)}",
        f"mouse_delta={_fmt_pair(result.mouse_delta)}",
        f"meas={_fmt_pair(result.measurement_offset)} filt={_fmt_pair(result.filtered_offset)} pred={_fmt_pair(result.predicted_offset)}",
        f"traj_end={_fmt_traj_end(result)}",
    ]
    if paused:
        lines.append("PAUSED: mouse output disabled")
    if kill_switch_active:
        lines.append("KILL SWITCH ACTIVE: F12 / ESC")

    y = 24
    for line in lines:
        cv2.putText(
            canvas,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        y += 22


def _draw_detections(
    canvas: np.ndarray,
    states: list[TargetState],
    selected: TargetState | None,
    center: tuple[int, int],
) -> None:
    cx, cy = center
    for state in states:
        is_selected = selected is not None and state is selected
        if state.cls_id == HEAD_CLS:
            color = (0, 0, 255)
        elif state.cls_id == BODY_CLS:
            color = (0, 255, 0)
        else:
            color = (0, 200, 255)
        if is_selected:
            color = (0, 64, 255)

        p1 = (int(round(state.x1)), int(round(state.y1)))
        p2 = (int(round(state.x2)), int(round(state.y2)))
        target = (int(round(state.target_x)), int(round(state.target_y)))
        cv2.rectangle(canvas, p1, p2, color, 2)
        cv2.circle(canvas, target, 4, color, -1)
        cv2.line(canvas, (cx, cy), target, (255, 255, 0), 1)
        label = f"{state.cls_name} dX:{state.delta_x:.1f} dY:{state.delta_y:.1f}"
        cv2.putText(
            canvas,
            label,
            (p1[0], max(p1[1] - 7, 14)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )


def _draw_target_marker(
    canvas: np.ndarray,
    selected: TargetState | None,
    center: tuple[int, int],
) -> None:
    if selected is None:
        return
    cv2.rectangle(
        canvas,
        (int(round(selected.x1)), int(round(selected.y1))),
        (int(round(selected.x2)), int(round(selected.y2))),
        (0, 0, 255),
        3,
    )
    tx = int(round(selected.target_x))
    ty = int(round(selected.target_y))
    cv2.circle(canvas, (tx, ty), 7, (0, 0, 255), 2)
    cv2.line(canvas, center, (tx, ty), (0, 0, 255), 2)


def _draw_prediction(
    canvas: np.ndarray,
    predicted_offset: tuple[float, float] | None,
    center: tuple[int, int],
) -> None:
    if predicted_offset is None:
        return
    px = int(round(center[0] + predicted_offset[0]))
    py = int(round(center[1] + predicted_offset[1]))
    cv2.circle(canvas, (px, py), 6, (0, 255, 255), -1)
    cv2.line(canvas, center, (px, py), (0, 255, 255), 1, cv2.LINE_AA)


def _draw_motion_vector(
    canvas: np.ndarray,
    mouse_delta: tuple[float, float] | None,
    center: tuple[int, int],
    result: AimPipelineResult,
) -> None:
    if mouse_delta is None:
        return
    end = (int(round(center[0] + mouse_delta[0])), int(round(center[1] + mouse_delta[1])))
    cv2.arrowedLine(canvas, center, end, (255, 128, 0), 2, cv2.LINE_AA, tipLength=0.2)

    if result.trajectory is not None:
        poly = [
            (int(round(center[0] + x)), int(round(center[1] + y)))
            for x, y in result.trajectory.points
        ]
        if len(poly) >= 2:
            cv2.polylines(canvas, [np.array(poly, dtype=np.int32)], False, (255, 128, 0), 2)


def _fmt_pair(value: tuple[float, float] | None) -> str:
    if value is None:
        return "None"
    return f"({value[0]:.1f}, {value[1]:.1f})"


def _selected_label(selected: TargetState | None) -> str:
    if selected is None:
        return "None"
    return f"{selected.cls_name}[{selected.cls_id}] conf={selected.conf:.2f}"


def _fmt_point(selected: TargetState | None) -> str:
    if selected is None:
        return "None"
    return f"({selected.target_x:.1f},{selected.target_y:.1f})"


def _fmt_traj_end(result: AimPipelineResult) -> str:
    if result.trajectory is None or not result.trajectory.points:
        return "None"
    x, y = result.trajectory.points[-1]
    return f"({x:.1f},{y:.1f})"
