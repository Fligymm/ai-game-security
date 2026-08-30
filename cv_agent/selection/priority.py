"""Priority / nearest-to-crosshair selection on TargetState lists."""

from __future__ import annotations

import math

from cv_agent.detection.target_state import BODY_CLS, HEAD_CLS, TargetState


def select_target(
    states: list[TargetState],
    *,
    prefer_head: bool = True,
    allow_body_fallback: bool = True,
) -> TargetState | None:
    """Pick the aim target with an explicit body-fallback policy."""
    if not states:
        return None

    def dist(s: TargetState) -> float:
        return math.hypot(s.delta_x, s.delta_y)

    heads = [s for s in states if s.cls_id == HEAD_CLS]
    bodies = [s for s in states if s.cls_id == BODY_CLS]
    if prefer_head and heads:
        return min(heads, key=dist)
    if allow_body_fallback and bodies:
        return min(bodies, key=dist)
    if not prefer_head and states:
        return min(states, key=dist)
    return None
