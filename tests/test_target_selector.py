from __future__ import annotations

from cv_agent.detection.target_state import TargetState
from cv_agent.control.target_selector import TargetSelectionConfig, TargetSelector


def make_target(x: float, y: float, *, conf: float, track_id: int | None) -> TargetState:
    size = 40.0
    return TargetState(
        x1=x - size / 2,
        y1=y - size / 2,
        x2=x + size / 2,
        y2=y + size / 2,
        conf=conf,
        cls_id=0,
        cls_name="enemy_head",
        target_x=x,
        target_y=y,
        screen_cx=320.0,
        screen_cy=320.0,
        delta_x=x - 320.0,
        delta_y=y - 320.0,
        frame_w=640,
        frame_h=640,
        track_id=track_id,
    )


def make_untracked(x: float, y: float, *, conf: float) -> TargetState:
    return make_target(x, y, conf=conf, track_id=None)


def test_sticky_lock_resists_small_target_advantage() -> None:
    selector = TargetSelector(TargetSelectionConfig(switching_threshold=0.12))
    old = make_target(300.0, 320.0, conf=0.90, track_id=1)
    near = make_target(350.0, 320.0, conf=0.91, track_id=2)
    assert selector.update([old, near]).track_id == 1
    near = make_target(312.0, 320.0, conf=0.91, track_id=2)
    assert selector.update([make_target(304.0, 320.0, conf=0.90, track_id=1), near]).track_id == 1
    assert selector.state.switch_count == 0


def test_missing_target_has_inertia_then_times_out() -> None:
    selector = TargetSelector(TargetSelectionConfig(lock_timeout_frames=3, strict_lock=False))
    old = make_target(300.0, 320.0, conf=0.90, track_id=1)
    assert selector.update([old]).track_id == 1
    assert selector.update([]).track_id == 1
    assert selector.update([]).track_id == 1
    assert selector.update([]) is None
    assert selector.state.current_locked_id is None


def test_close_scores_do_not_switch_after_long_jitter_window() -> None:
    selector = TargetSelector(
        TargetSelectionConfig(
            min_lock_frames=10,
            switch_confirm_frames=5,
            switch_cooldown_frames=20,
        )
    )
    old = make_target(295.0, 320.0, conf=0.90, track_id=1)
    other = make_target(350.0, 320.0, conf=0.91, track_id=2)
    assert selector.update([old, other]).track_id == 1
    for index in range(60):
        old_now = make_target(298.0 + (index % 2), 320.0, conf=0.90, track_id=1)
        other_now = make_target(348.0 - (index % 2), 320.0, conf=0.91, track_id=2)
        assert selector.update([old_now, other_now]).track_id == 1
    assert selector.state.switch_count == 0


def test_nearer_head_can_replace_farther_head_after_confirmation() -> None:
    selector = TargetSelector(
        TargetSelectionConfig(
            min_lock_frames=0,
            switch_confirm_frames=3,
            hysteresis_bonus=0.35,
            clear_distance_ratio=0.65,
            strict_lock=False,
        )
    )
    far = make_target(440.0, 320.0, conf=0.99, track_id=1)
    near = make_target(300.0, 320.0, conf=0.90, track_id=2)
    assert selector.update([far]).track_id == 1
    for _ in range(3):
        assert selector.update([far, near]).track_id in (1, 2)
    assert selector.state.current_locked_id == 2


def test_strict_lock_never_targets_another_visible_target() -> None:
    selector = TargetSelector(
        TargetSelectionConfig(strict_lock=True, lock_timeout_frames=3)
    )
    first = make_target(280.0, 320.0, conf=0.70, track_id=1)
    other = make_target(321.0, 320.0, conf=0.99, track_id=2)
    assert selector.update([first, other]).track_id == 2
    assert selector.update([first, other]).track_id == 2
    assert selector.state.switch_count == 0


def test_strict_lock_emits_no_target_while_active_target_is_missing() -> None:
    selector = TargetSelector(
        TargetSelectionConfig(strict_lock=True, lock_timeout_frames=3)
    )
    first = make_target(280.0, 320.0, conf=0.90, track_id=1)
    other = make_target(321.0, 320.0, conf=0.99, track_id=2)
    assert selector.update([first]).track_id == 1
    assert selector.update([other]) is None
    assert selector.update([other]) is None
    assert selector.update([other]).track_id == 2


def test_untracked_targets_do_not_recycle_active_id_when_ambiguous() -> None:
    selector = TargetSelector(
        TargetSelectionConfig(strict_lock=True, lock_timeout_frames=3)
    )
    assert selector.update([make_untracked(260.0, 320.0, conf=0.9), make_untracked(380.0, 320.0, conf=0.9)]).track_id == 1
    # Both detections are equally close to the previous active position; the
    # selector must hold output instead of assigning ID 1 to the other target.
    assert selector.update([make_untracked(320.0, 320.0, conf=0.9), make_untracked(320.0, 320.0, conf=0.9)]) is None
    assert selector.state.current_locked_id == 1
