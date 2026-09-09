"""Unit tests for distance-first and strict-lock target selection."""
from __future__ import annotations

import unittest

from cv_agent.detection.target_state import TargetState
from cv_agent.selection.priority import TargetSelectionConfig, TargetSelector


def mock_target(x: float, y: float, *, track_id: int | None = None, conf: float = 0.9) -> TargetState:
    size = 20.0
    return TargetState(
        x1=x - size / 2, y1=y - size / 2, x2=x + size / 2, y2=y + size / 2,
        conf=conf, cls_id=0, cls_name="enemy_head", target_x=x, target_y=y,
        screen_cx=320.0, screen_cy=320.0, delta_x=x - 320.0, delta_y=y - 320.0,
        frame_w=640, frame_h=640, track_id=track_id,
    )


class PrioritySelectionTests(unittest.TestCase):
    def test_distance_priority_without_lock(self) -> None:
        selector = TargetSelector(TargetSelectionConfig(strict_lock=False))
        far = mock_target(250, 250, track_id=1, conf=0.99)
        near = mock_target(315, 318, track_id=2, conf=0.5)
        selected = selector.update([far, near])
        self.assertIsNotNone(selected)
        self.assertEqual(selected.track_id, 2)

    def test_strict_lock_does_not_switch_to_closer_target(self) -> None:
        selector = TargetSelector(TargetSelectionConfig(strict_lock=True, lock_timeout_frames=3))
        target_a = mock_target(280, 320, track_id=1)
        target_b = mock_target(321, 320, track_id=2, conf=0.99)
        self.assertEqual(selector.update([target_a]).track_id, 1)
        self.assertEqual(selector.update([target_a, target_b]).track_id, 1)
        self.assertEqual(selector.state.current_locked_id, 1)

    def test_strict_lock_holds_during_timeout_then_clears(self) -> None:
        selector = TargetSelector(TargetSelectionConfig(strict_lock=True, lock_timeout_frames=3))
        target_a = mock_target(280, 320, track_id=1)
        target_b = mock_target(321, 320, track_id=2)
        self.assertEqual(selector.update([target_a]).track_id, 1)
        self.assertIsNone(selector.update([target_b]))
        self.assertIsNone(selector.update([target_b]))
        # The third missing frame reaches the timeout and permits reacquisition.
        reacquired = selector.update([target_b])
        self.assertEqual(reacquired.track_id, 2)
        self.assertEqual(selector.state.current_locked_id, 2)

    def test_missing_target_with_no_detections_clears_lock(self) -> None:
        selector = TargetSelector(TargetSelectionConfig(strict_lock=True, lock_timeout_frames=2))
        self.assertEqual(selector.update([mock_target(280, 320, track_id=7)]).track_id, 7)
        self.assertIsNone(selector.update([]))
        self.assertIsNone(selector.update([]))
        self.assertIsNone(selector.state.current_locked_id)


if __name__ == "__main__":
    unittest.main()
