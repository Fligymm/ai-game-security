"""Distance-first target selection with sticky lock hysteresis."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from cv_agent.detection.target_state import BODY_CLS, HEAD_CLS, TargetState


@dataclass(frozen=True)
class TargetSelectionConfig:
    distance_weight: float = 0.80
    confidence_weight: float = 0.10
    head_weight: float = 0.10
    hysteresis_bonus: float = 0.30
    switching_threshold: float = 0.10
    lock_timeout_frames: int = 5
    association_radius: float = 90.0
    roi_radius: float | None = None
    min_lock_frames: int = 15
    switch_confirm_frames: int = 5
    switch_cooldown_frames: int = 20
    clear_distance_ratio: float = 0.65
    strict_lock: bool = True
    ambiguous_match_margin: float = 8.0
    require_external_track_id: bool = False

    def __post_init__(self) -> None:
        if min(self.distance_weight, self.confidence_weight, self.head_weight) < 0:
            raise ValueError("selection weights must be non-negative")
        if self.distance_weight + self.confidence_weight + self.head_weight <= 0:
            raise ValueError("at least one selection weight must be positive")
        if self.hysteresis_bonus < 0 or self.switching_threshold < 0:
            raise ValueError("hysteresis values must be non-negative")
        if self.lock_timeout_frames < 1 or self.association_radius <= 0:
            raise ValueError("invalid lock timeout or association radius")
        if self.min_lock_frames < 0 or self.switch_confirm_frames < 1 or self.switch_cooldown_frames < 0:
            raise ValueError("invalid switch stabilization configuration")
        if not 0.0 < self.clear_distance_ratio < 1.0:
            raise ValueError("clear_distance_ratio must be in (0, 1)")


@dataclass
class TargetLockState:
    current_locked_id: int | None = None
    missing_frames: int = 0
    next_id: int = 1
    previous: dict[int, TargetState] = field(default_factory=dict)
    switch_count: int = 0
    consecutive_lock_frames: int = 0
    lock_age_frames: int = 0
    pending_switch_id: int | None = None
    pending_switch_frames: int = 0
    switch_cooldown: int = 0


class TargetSelector:
    """Stateful selector that resists frame-to-frame target oscillation."""

    def __init__(self, config: TargetSelectionConfig | None = None, **legacy: object) -> None:
        if config is None:
            strict_lock = bool(legacy.pop("strict_lock", False if legacy else True))
            config = TargetSelectionConfig(
                hysteresis_bonus=float(legacy.pop("lock_bonus", 0.30)),
                lock_timeout_frames=int(legacy.pop("max_missing_frames", 5)),
                switching_threshold=float(legacy.pop("switching_threshold", 0.10)),
                strict_lock=strict_lock,
            )
            if "switch_ratio" in legacy:
                # Preserve the old constructor without changing the new additive rule.
                ratio = float(legacy.pop("switch_ratio"))
                config = TargetSelectionConfig(
                    **{**config.__dict__, "switching_threshold": max(config.switching_threshold, ratio - 1.0)}
                )
        if legacy:
            raise TypeError(f"unexpected selector options: {sorted(legacy)}")
        self.config = config
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
        if self.config.require_external_track_id and any(item.track_id is None for item in candidates):
            return None
        assigned = self._assign_ids(candidates)

        # Strict-lock mode never retargets while the active target is visible.
        # If it disappears, return no target so the controller emits no move.
        if self.config.strict_lock and self.state.current_locked_id is not None:
            current = next(
                (item for item in assigned if item.track_id == self.state.current_locked_id),
                None,
            )
            if current is not None:
                self.state.missing_frames = 0
                self.state.lock_age_frames += 1
                self.state.previous = {
                    item.track_id: item for item in assigned if item.track_id is not None
                }
                self._clear_pending_switch()
                return current
            self.state.missing_frames += 1
            if self.state.missing_frames < self.config.lock_timeout_frames:
                return None
            self.state.current_locked_id = None
            self.state.previous = {}
            self.state.consecutive_lock_frames = 0
            self.state.lock_age_frames = 0
            self._clear_pending_switch()
            assigned = self._assign_ids(candidates)

        if not assigned:
            self.state.missing_frames += 1
            if self.state.current_locked_id is not None and self.state.missing_frames < self.config.lock_timeout_frames:
                return self.state.previous.get(self.state.current_locked_id)
            self.state.current_locked_id = None
            self.state.previous = {}
            self.state.consecutive_lock_frames = 0
            self.state.lock_age_frames = 0
            self._clear_pending_switch()
            return None

        self.state.missing_frames = 0
        self.state.switch_cooldown = max(0, self.state.switch_cooldown - 1)
        # Find the raw best candidate first; hysteresis must not hide a better
        # candidate from the switch-confirmation state machine.
        scored = [(self.score(item, include_hysteresis=False), item) for item in assigned]
        best_score, best = max(scored, key=lambda pair: pair[0])
        if self.state.current_locked_id is None:
            # Initial acquisition is distance-first; confidence and head class
            # only break near-distance ties.
            best = min(
                assigned,
                key=lambda item: (
                    math.hypot(item.delta_x, item.delta_y),
                    -float(item.conf),
                    -(1 if item.cls_id == HEAD_CLS else 0),
                ),
            )
            best_score = self.score(best, include_hysteresis=False)
        current = next((item for item in assigned if item.track_id == self.state.current_locked_id), None)
        if current is not None and best.track_id != current.track_id:
            current_score = self.score(current, include_hysteresis=False)
            advantage = best_score - current_score
            distance_break = self._distance_breakthrough(current, best)
            can_consider = self.state.lock_age_frames >= self.config.min_lock_frames
            if self.state.switch_cooldown > 0 and not distance_break:
                can_consider = False
            if not can_consider or (advantage <= self.config.switching_threshold and not distance_break):
                self._clear_pending_switch()
                best = current
            else:
                if self.state.pending_switch_id != best.track_id:
                    self.state.pending_switch_id = best.track_id
                    self.state.pending_switch_frames = 1
                else:
                    self.state.pending_switch_frames += 1
                if self.state.pending_switch_frames < self.config.switch_confirm_frames:
                    best = current
        else:
            self._clear_pending_switch()

        if self.state.current_locked_id is not None and best.track_id != self.state.current_locked_id:
            self.state.switch_count += 1
            self.state.consecutive_lock_frames = 0
            self.state.lock_age_frames = 0
            self.state.switch_cooldown = self.config.switch_cooldown_frames
        else:
            self.state.lock_age_frames += 1
        self.state.current_locked_id = best.track_id
        self.state.consecutive_lock_frames += 1
        self.state.previous = {item.track_id: item for item in assigned if item.track_id is not None}
        return best

    def _clear_pending_switch(self) -> None:
        self.state.pending_switch_id = None
        self.state.pending_switch_frames = 0

    def _distance_breakthrough(self, current: TargetState, candidate: TargetState) -> bool:
        """Allow a materially closer target of the same semantic class to win."""
        if current.cls_id != candidate.cls_id:
            return False
        current_distance = math.hypot(current.delta_x, current.delta_y)
        candidate_distance = math.hypot(candidate.delta_x, candidate.delta_y)
        return candidate_distance <= current_distance * self.config.clear_distance_ratio

    def score(self, state: TargetState, *, include_hysteresis: bool = True) -> float:
        diagonal = max(math.hypot(state.frame_w, state.frame_h), 1.0)
        radius = self.config.roi_radius or diagonal
        distance_score = max(0.0, 1.0 - math.hypot(state.delta_x, state.delta_y) / radius)
        head_score = 1.0 if state.cls_id == HEAD_CLS else 0.0
        score = (
            self.config.distance_weight * distance_score
            + self.config.confidence_weight * max(0.0, min(1.0, state.conf))
            + self.config.head_weight * head_score
        )
        if include_hysteresis and state.track_id == self.state.current_locked_id:
            score += self.config.hysteresis_bonus
        return float(score)

    def _assign_ids(self, states: list[TargetState]) -> list[TargetState]:
        available = dict(self.state.previous)
        assigned: list[TargetState] = []
        ordered_states = list(states)
        # Preserve the active lock before assigning the remaining detections.
        # Sorting all detections by crosshair distance can otherwise give the
        # active ID to a different target when both targets approach center.
        if self.state.current_locked_id is not None:
            active_old = available.get(self.state.current_locked_id)
            if active_old is not None:
                matching = [
                    (math.hypot(item.target_x - active_old.target_x, item.target_y - active_old.target_y), index, item)
                    for index, item in enumerate(ordered_states)
                    if item.cls_id == active_old.cls_id and item.track_id is None
                ]
                if matching:
                    matching.sort(key=lambda item: item[0])
                    nearest_distance, nearest_index, nearest = matching[0]
                    second_distance = matching[1][0] if len(matching) > 1 else float("inf")
                    if nearest_distance <= self.config.association_radius and (
                        second_distance - nearest_distance >= self.config.ambiguous_match_margin
                        or len(matching) == 1
                    ):
                        ordered_states.insert(0, replace(nearest, track_id=self.state.current_locked_id))
                        ordered_states.pop(nearest_index + 1)
                        available.pop(self.state.current_locked_id, None)
                    else:
                        # Do not recycle the active ID onto an ambiguous or
                        # distant detection; strict mode will hold output.
                        available.pop(self.state.current_locked_id, None)

        for state in ordered_states:
            track_id = state.track_id
            if track_id is None:
                matches = [
                    (math.hypot(state.target_x - old.target_x, state.target_y - old.target_y), old_id)
                    for old_id, old in available.items()
                    if old.cls_id == state.cls_id
                ]
                if matches:
                    distance, old_id = min(matches)
                    if distance <= self.config.association_radius:
                        track_id = old_id
                        available.pop(old_id, None)
            if track_id is None:
                track_id = self.state.next_id
                self.state.next_id += 1
            assigned.append(replace(state, track_id=track_id))
        return assigned


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
    """Backward-compatible one-shot selection."""
    return TargetSelector().update(states, prefer_head=prefer_head, allow_body_fallback=allow_body_fallback)
