"""Typed detection model emitted by vision detectors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Detection:
    """One detector output box in pixel or normalized coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    cls_id: int

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.x1, self.y1, self.x2, self.y2

    @property
    def row(self) -> list[float | int]:
        return [self.x1, self.y1, self.x2, self.y2, self.conf, self.cls_id]

    def __iter__(self):
        yield from (self.x1, self.y1, self.x2, self.y2, self.conf, self.cls_id)

    def __len__(self) -> int:
        return 6

