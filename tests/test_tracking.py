from dataclasses import dataclass
from vision.tracking import KalmanTracker

@dataclass
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float
    cls_id: int

    @property
    def bbox(self):
        return self.x1, self.y1, self.x2, self.y2

def det(x: float, y: float, size: float = 10.0) -> Detection:
    return Detection(x, y, x + size, y + size, 0.9, 1)


def test_ids_are_stable_and_unique():
    tracker = KalmanTracker(iou_threshold=0.1)
    first = tracker.update([det(0, 0), det(100, 100)])
    second = tracker.update([det(2, 1), det(102, 101)])
    assert {item.track_id for item in first} == {1, 2}
    assert {item.track_id for item in second} == {1, 2}


def test_occlusion_recovery_and_expiry():
    tracker = KalmanTracker(max_disappeared=2, iou_threshold=0.1)
    initial = tracker.update([det(0, 0)])[0]
    tracker.update([])
    recovered = tracker.update([det(2, 0)])[0]
    assert recovered.track_id == initial.track_id
    tracker.update([])
    tracker.update([])
    expired = tracker.update([])
    assert expired == []
    assert tracker.update([det(2, 0)])[0].track_id != initial.track_id
