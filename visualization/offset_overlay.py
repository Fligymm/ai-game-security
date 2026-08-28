"""Draw crosshair, box centers, and ΔX/ΔY offset vectors on a BGR frame."""

from __future__ import annotations

import cv2
import numpy as np

from cv_agent.detection.target_state import TargetState
from cv_agent.trajectory.paths import Trajectory


def draw_offset_overlay(
    frame: np.ndarray,
    states: list[TargetState],
    selected: TargetState | None = None,
    trajectory: Trajectory | None = None,
) -> np.ndarray:
    canvas = frame.copy()
    if not states:
        return canvas

    cx = int(round(states[0].screen_cx))
    cy = int(round(states[0].screen_cy))
    cv2.drawMarker(
        canvas,
        (cx, cy),
        (255, 0, 0),
        markerType=cv2.MARKER_CROSS,
        markerSize=16,
        thickness=2,
    )

    for state in states:
        color = (0, 255, 255) if selected is not None and state is selected else (0, 255, 0)
        p1 = (int(round(state.x1)), int(round(state.y1)))
        p2 = (int(round(state.x2)), int(round(state.y2)))
        tx, ty = int(round(state.target_x)), int(round(state.target_y))
        cv2.rectangle(canvas, p1, p2, color, 2)
        cv2.circle(canvas, (tx, ty), 4, (0, 0, 255), -1)
        cv2.line(canvas, (cx, cy), (tx, ty), (0, 255, 255), 1)
        label = f"{state.cls_name} | dX:{state.delta_x:.1f} dY:{state.delta_y:.1f}"
        cv2.putText(
            canvas,
            label,
            (p1[0], max(p1[1] - 8, 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )

    if trajectory is not None and selected is not None:
        origin = np.array([selected.screen_cx, selected.screen_cy], dtype=np.float64)
        poly = [
            (int(round(origin[0] + x)), int(round(origin[1] + y)))
            for x, y in trajectory.points
        ]
        if len(poly) >= 2:
            cv2.polylines(canvas, [np.array(poly, dtype=np.int32)], False, (255, 128, 0), 2)

    return canvas
