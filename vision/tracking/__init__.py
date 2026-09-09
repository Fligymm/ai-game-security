"""Multi-object tracking, ID assignment, and occlusion recovery."""
from .base_tracker import BaseTracker, DetectionResult, TrackedTarget
from .kalman_tracker import KalmanTracker

__all__ = ["BaseTracker", "DetectionResult", "TrackedTarget", "KalmanTracker"]
