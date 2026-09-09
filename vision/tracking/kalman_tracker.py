"""Lightweight constant-velocity Kalman-style IOU tracker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .base_tracker import BaseTracker, DetectionResult, TrackedTarget, intersection_over_union


@dataclass
class _Track:
    target: TrackedTarget
    vx: float = 0.0
    vy: float = 0.0
    lost: int = 0

    def predict(self) -> tuple[float, float, float, float]:
        return (self.target.x1 + self.vx, self.target.y1 + self.vy,
                self.target.x2 + self.vx, self.target.y2 + self.vy)


class KalmanTracker(BaseTracker):
    """Greedy IOU association with constant-velocity state prediction."""

    def __init__(self, *, max_disappeared: int = 10, iou_threshold: float = 0.3) -> None:
        super().__init__(max_disappeared=max_disappeared, iou_threshold=iou_threshold)
        self._tracks: dict[int, _Track] = {}
        self._next_id = 1

    def update(self, detections: List[DetectionResult]) -> List[TrackedTarget]:
        if detections is None:
            raise TypeError("detections must be a list")
        detections = list(detections)
        predictions = {tid: track.predict() for tid, track in self._tracks.items()}
        pairs = sorted(
            ((intersection_over_union(pred, det.bbox), tid, idx)
             for tid, pred in predictions.items() for idx, det in enumerate(detections)),
            reverse=True,
        )
        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()
        for score, tid, idx in pairs:
            if score < self.iou_threshold or tid in matched_tracks or idx in matched_dets:
                continue
            track = self._tracks[tid]
            det = detections[idx]
            old = track.target
            old_cx, old_cy = old.center
            new_cx, new_cy = ((det.x1 + det.x2) / 2, (det.y1 + det.y2) / 2)
            track.vx, track.vy = new_cx - old_cx, new_cy - old_cy
            track.lost = 0
            track.target = TrackedTarget(tid, det.x1, det.y1, det.x2, det.y2, det.conf, det.cls_id, 0)
            matched_tracks.add(tid)
            matched_dets.add(idx)
        for tid, track in list(self._tracks.items()):
            if tid not in matched_tracks:
                track.lost += 1
                track.target = TrackedTarget(tid, *track.predict(), track.target.conf, track.target.cls_id, track.lost)
                if track.lost > self.max_disappeared:
                    del self._tracks[tid]
        for idx, det in enumerate(detections):
            if idx not in matched_dets:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = _Track(TrackedTarget(tid, det.x1, det.y1, det.x2, det.y2, det.conf, det.cls_id, 0))
        return [track.target for track in self._tracks.values()]


__all__ = ["KalmanTracker"]
