"""Distance-aware target selection with lock hysteresis."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from cv_agent.detection.target_state import BODY_CLS, HEAD_CLS, TargetState


@dataclass
class TargetLockState:
    current_locked_id: int | None = None
    missing_frames: int = 0
    next_id: int = 1
    previous: dict[int, TargetState] = field(default_factory=dict)
    switch_count: int = 0
    consecutive_lock_frames: int = 0


class TargetSelector:
    """Select targets while penalizing unnecessary lock switches."""

    def __init__(
        self,
        *,
        area_weight: float = 0.45,
        distance_weight: float = 0.55,
        lock_bonus: float = 0.15,
        switch_ratio: float = 1.5,
        max_missing_frames: int = 5,
        association_radius: float = 90.0,
    ) -> None:
        if area_weight < 0 or distance_weight < 0 or area_weight + distance_weight <= 0:
            raise ValueError("area_weight and distance_weight must be non-negative and non-zero")
        if switch_ratio <= 1.0 or max_missing_frames < 1 or association_radius <= 0:
            raise ValueError("invalid hysteresis configuration")
        self.area_weight = float(area_weight)
        self.distance_weight = float(distance_weight)
        self.lock_bonus = float(lock_bonus)
        self.switch_ratio = float(switch_ratio)
        self.max_missing_frames = int(max_missing_frames)
        self.association_radius = float(association_radius)
        self.state = TargetLockState()

    def reset(self) -> None:
        self.state = TargetLockState()

    def update(
        self,
        states: list[TargetState],
        *,
        prefer_head: bool = True,
        allow_body_fallback: bool = True,
    ) -> TargetState | None:
        candidates = _eligible(states, prefer_head, allow_body_fallback)
        assigned = self._assign_ids(candidates)
        if not assigned:
            self.state.missing_frames += 1
            if self.state.missing_frames < self.max_missing_frames:
                return None
            self.state.current_locked_id = None
            self.state.previous = {}
            return None

        self.state.missing_frames = 0
        scored = [(self.score(item), item) for item in assigned]
        best_score, best = max(scored, key=lambda pair: pair[0])
        current = next(
            (item for item in assigned if item.track_id == self.state.current_locked_id),
            None,
        )
        if current is not None:
            current_score = self.score(current, include_lock_bonus=False)
            if best.track_id != current.track_id and best_score < max(current_score * self.switch_ratio, current_score + 1e-6):
                best = current
        if self.state.current_locked_id is not None and best.track_id != self.state.current_locked_id:
            self.state.switch_count += 1
            self.state.consecutive_lock_frames = 0
        self.state.current_locked_id = best.track_id
        self.state.consecutive_lock_frames += 1
        self.state.previous = {int(item.track_id): item for item in assigned if item.track_id is not None}
        return best

    def score(self, state: TargetState, *, include_lock_bonus: bool = True) -> float:
        tracked = list(self.state.previous.values()) + [state]
        max_area = max((_area(item) for item in tracked), default=1.0)
        diagonal = max(math.hypot(state.frame_w, state.frame_h), 1.0)
        proximity = max(0.0, 1.0 - math.hypot(state.delta_x, state.delta_y) / diagonal)
        area_score = math.log1p(_area(state)) / max(math.log1p(max_area), 1e-9)
        total = self.area_weight + self.distance_weight
        value = (area_score * self.area_weight + proximity * self.distance_weight) / total
        if include_lock_bonus and state.track_id == self.state.current_locked_id:
            value += self.lock_bonus
        return float(value)

    def _assign_ids(self, states: list[TargetState]) -> list[TargetState]:
        available = dict(self.state.previous)
        assigned: list[TargetState] = []
        for state in sorted(states, key=lambda item: math.hypot(item.delta_x, item.delta_y)):
            track_id = state.track_id
            if track_id is None:
                matches = [
                    (math.hypot(state.target_x - old.target_x, state.target_y - old.target_y), old_id)
                    for old_id, old in available.items()
                    if old.cls_id == state.cls_id
                ]
                if matches:
                    distance, old_id = min(matches)
                    if distance <= self.association_radius:
                        track_id = old_id
                        available.pop(old_id, None)
            if track_id is None:
                track_id = self.state.next_id
                self.state.next_id += 1
            assigned.append(replace(state, track_id=track_id))
        return assigned


def _area(state: TargetState) -> float:
    return max(0.0, (state.x2 - state.x1) * (state.y2 - state.y1))


def _eligible(states: list[TargetState], prefer_head: bool, allow_body_fallback: bool) -> list[TargetState]:
    if prefer_head:
        heads = [state for state in states if state.cls_id == HEAD_CLS]
        if heads:
            return heads
    if allow_body_fallback:
        bodies = [state for state in states if state.cls_id == BODY_CLS]
        if bodies:
            return bodies
    return states if not prefer_head else []


def select_target(
    states: list[TargetState],
    *,
    prefer_head: bool = True,
    allow_body_fallback: bool = True,
) -> TargetState | None:
    """Pick the aim target with an explicit body-fallback policy."""
    selector = TargetSelector()
    return selector.update(
        states,
        prefer_head=prefer_head,
        allow_body_fallback=allow_body_fallback,
    )
