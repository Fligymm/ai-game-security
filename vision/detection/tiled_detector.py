"""Tile a full-resolution frame before running a small-ROI-trained detector.

The frozen CS2 detector was trained on 320x320 ROI crops. Running it directly
on a 1920x1080 first-person frame shrinks targets and causes a large recall drop.
This wrapper preserves the detector unchanged and merges detections from a
fixed grid, with class-aware NMS to remove tile-overlap duplicates.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from vision.detection.detection import Detection


class _Detector(Protocol):
    class_names: dict[int, str]

    def detect_frame(self, frame: np.ndarray) -> list[Detection]: ...


def _tile_starts(length: int, tile: int, count: int) -> list[int]:
    if length <= tile or count <= 1:
        return [0]
    last = length - tile
    return sorted({int(round(index * last / (count - 1))) for index in range(count)})


def _iou(a: Detection, b: Detection) -> float:
    ix1 = max(a.x1, b.x1)
    iy1 = max(a.y1, b.y1)
    ix2 = min(a.x2, b.x2)
    iy2 = min(a.y2, b.y2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, a.x2 - a.x1) * max(0.0, a.y2 - a.y1)
    area_b = max(0.0, b.x2 - b.x1) * max(0.0, b.y2 - b.y1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def class_aware_nms(detections: list[Detection], iou_threshold: float = 0.5) -> list[Detection]:
    """Greedy NMS that only suppresses boxes of the same class."""

    ordered = sorted(detections, key=lambda det: det.conf, reverse=True)
    kept: list[Detection] = []
    for candidate in ordered:
        if any(
            candidate.cls_id == existing.cls_id
            and _iou(candidate, existing) > iou_threshold
            for existing in kept
        ):
            continue
        kept.append(candidate)
    return kept


class TiledDetector:
    """Run a detector over a grid and return full-frame coordinates."""

    def __init__(
        self,
        detector: _Detector,
        *,
        tile_size: int = 720,
        grid: int = 3,
        nms_iou: float = 0.5,
    ) -> None:
        if tile_size <= 0 or grid <= 0:
            raise ValueError("tile_size and grid must be positive")
        self.detector = detector
        self.tile_size = int(tile_size)
        self.grid = int(grid)
        self.nms_iou = float(nms_iou)

    @property
    def class_names(self) -> dict[int, str]:
        return self.detector.class_names

    def detect_frame(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        tile_w = min(self.tile_size, width)
        tile_h = min(self.tile_size, height)
        xs = _tile_starts(width, tile_w, self.grid)
        ys = _tile_starts(height, tile_h, self.grid)
        merged: list[Detection] = []
        for y in ys:
            for x in xs:
                tile = frame[y : y + tile_h, x : x + tile_w]
                if tile.size == 0:
                    continue
                for det in self.detector.detect_frame(tile):
                    merged.append(
                        Detection(
                            x1=float(det.x1 + x),
                            y1=float(det.y1 + y),
                            x2=float(det.x2 + x),
                            y2=float(det.y2 + y),
                            conf=float(det.conf),
                            cls_id=int(det.cls_id),
                            track_id=det.track_id,
                        )
                    )
        return class_aware_nms(merged, self.nms_iou)


__all__ = ["TiledDetector", "class_aware_nms"]