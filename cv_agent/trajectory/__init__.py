"""Aim, camera, and target-tracking trajectory generation."""

from .paths import GENERATORS, Trajectory, generate, smoothness_features

__all__ = ["GENERATORS", "Trajectory", "generate", "smoothness_features"]
