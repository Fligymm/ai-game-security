"""Player, head, and target detection on game frames."""

from .detection import Detection
from .yolo_detector import YOLODetector

__all__ = ["Detection", "YOLODetector"]
