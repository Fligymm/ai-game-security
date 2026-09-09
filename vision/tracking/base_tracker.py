"""Common types and interface for multi-object trackers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Protocol, Sequence


class DetectionResult(Protocol):
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    cls_id: int

    @property
    def bbox(self) -> tuple[float, float, float, float]: ...


@dataclass(frozen=True, slots=True)
class TrackedTarget:
    track_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    cls_id: int
    lost_frames: int = 0

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.x1, self.y1, self.x2, self.y2

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


class BaseTracker(ABC):
    def __init__(self, *, max_disappeared: int = 10, iou_threshold: float = 0.3) -> None:
        if max_disappeared < 0 or not 0.0 <= iou_threshold <= 1.0:
            raise ValueError("invalid tracker configuration")
        self.max_disappeared = int(max_disappeared)
        self.iou_threshold = float(iou_threshold)

    @abstractmethod
    def update(self, detections: List[DetectionResult]) -> List[TrackedTarget]:
        """Associate detections with existing tracks and return active targets."""


def intersection_over_union(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / (area_a + area_b - inter) if area_a + area_b > inter else 0.0


__all__ = ["BaseTracker", "DetectionResult", "TrackedTarget", "intersection_over_union"]
