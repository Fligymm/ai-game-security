"""Offline CV-based assistance simulation (research-only, isolated environments)."""

from cv_agent.control import AimController
from cv_agent.detection import TargetState, detections_to_states
from cv_agent.prediction import Kalman2D
from cv_agent.selection import select_target
from cv_agent.trajectory import generate, smoothness_features

__all__ = [
    "AimController",
    "Kalman2D",
    "TargetState",
    "detections_to_states",
    "generate",
    "select_target",
    "smoothness_features",
]
