"""Bind YOLODetector boxes to screen-relative target state (ΔX, ΔY)."""

from __future__ import annotations

from dataclasses import dataclass

from vision.detection.detection import Detection

HEAD_CLS = 0  # data.yaml: enemy_head
BODY_CLS = 1  # data.yaml: enemy_body


@dataclass(frozen=True)
class TargetState:
    """One detection mapped to crosshair-relative offset."""

    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    cls_id: int
    cls_name: str
    target_x: float
    target_y: float
    screen_cx: float
    screen_cy: float
    delta_x: float
    delta_y: float
    frame_w: int
    frame_h: int

    @property
    def offset(self) -> tuple[float, float]:
        return self.delta_x, self.delta_y


def screen_center(width: int, height: int) -> tuple[float, float]:
    return width / 2.0, height / 2.0


def bbox_center(x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def relative_offset(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: int,
    height: int,
) -> tuple[float, float, float, float, float, float]:
    """Return (tx, ty, cx, cy, dx, dy) in pixels."""
    cx, cy = screen_center(width, height)
    tx, ty = bbox_center(x1, y1, x2, y2)
    return tx, ty, cx, cy, tx - cx, ty - cy


def detection_to_state(
    det: Detection | list[float | int] | tuple[float | int, ...],
    frame_shape: tuple[int, ...],
    class_names: dict[int, str] | None = None,
) -> TargetState:
    """Convert one detector output into TargetState."""
    if isinstance(det, Detection):
        x1, y1, x2, y2, conf, cls_id = det.row
    else:
        x1, y1, x2, y2, conf, cls_id = det
    x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
    height, width = int(frame_shape[0]), int(frame_shape[1])
    tx, ty, cx, cy, dx, dy = relative_offset(x1, y1, x2, y2, width, height)
    cls_id_i = int(cls_id)
    names = class_names or {HEAD_CLS: "enemy_head", BODY_CLS: "enemy_body"}
    return TargetState(
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        conf=float(conf),
        cls_id=cls_id_i,
        cls_name=str(names.get(cls_id_i, str(cls_id_i))),
        target_x=tx,
        target_y=ty,
        screen_cx=cx,
        screen_cy=cy,
        delta_x=dx,
        delta_y=dy,
        frame_w=width,
        frame_h=height,
    )


def detections_to_states(
    detections: list[Detection | list[float | int] | tuple[float | int, ...]],
    frame_shape: tuple[int, ...],
    class_names: dict[int, str] | None = None,
) -> list[TargetState]:
    return [detection_to_state(d, frame_shape, class_names) for d in detections]
