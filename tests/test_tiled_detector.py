from __future__ import annotations

import numpy as np

from vision.detection.detection import Detection
from vision.detection.tiled_detector import TiledDetector, class_aware_nms


class _FixedDetector:
    class_names = {0: "enemy_head", 1: "enemy_body"}

    def __init__(self, box: tuple[float, float, float, float], conf: float = 0.9) -> None:
        self.box = box
        self.conf = conf

    def detect_frame(self, frame):
        x1, y1, x2, y2 = self.box
        return [Detection(x1, y1, x2, y2, self.conf, 0)]


def test_tiled_detector_offsets_boxes_and_nms() -> None:
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    detector = TiledDetector(_FixedDetector((0, 0, 5, 5)), tile_size=60, grid=2)
    detections = detector.detect_frame(frame)
    # Two tiles per axis => four distinct global boxes.
    assert len(detections) == 4
    assert all(det.cls_id == 0 for det in detections)
    assert any(det.x1 > 0 for det in detections)
    assert any(det.y1 > 0 for det in detections)


def test_class_aware_nms_keeps_different_classes() -> None:
    same_class_high = Detection(0, 0, 10, 10, 0.9, 0)
    same_class_low = Detection(1, 1, 11, 11, 0.8, 0)
    other_class = Detection(1, 1, 11, 11, 0.7, 1)
    kept = class_aware_nms([same_class_low, same_class_high, other_class])
    assert kept == [same_class_high, other_class]