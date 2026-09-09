"""Target selection: nearest, in-view, priority, and switching."""

from .priority import TargetLockState, TargetSelector, TargetSelectionConfig, select_target

__all__ = ["TargetLockState", "TargetSelector", "TargetSelectionConfig", "select_target"]
