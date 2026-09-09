"""Target selection: nearest, in-view, priority, and switching."""

from .priority import TargetLockState, TargetSelector, select_target

__all__ = ["TargetLockState", "TargetSelector", "select_target"]
