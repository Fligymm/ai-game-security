from __future__ import annotations

import unittest

import numpy as np

from cv_agent.detection.target_state import TargetState
from cv_agent.selection.priority import TargetSelector
from cv_agent.trajectory.paths import generate


def state(x: float, y: float, size: float, track_id: int | None = None) -> TargetState:
    return TargetState(
        x1=x - size / 2,
        y1=y - size / 2,
        x2=x + size / 2,
        y2=y + size / 2,
        conf=0.9,
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


class SelectionAndTrajectoryTests(unittest.TestCase):
    def test_lock_does_not_flicker_for_small_score_change(self) -> None:
        selector = TargetSelector(switch_ratio=1.5)
        first = selector.update([state(300, 320, 40), state(340, 320, 39)])
        self.assertIsNotNone(first)
        locked_id = first.track_id
        second = selector.update([state(301, 320, 40), state(315, 320, 41)])
        self.assertEqual(second.track_id, locked_id)

    def test_lock_can_switch_after_missing_threshold(self) -> None:
        selector = TargetSelector(max_missing_frames=3)
        first = selector.update([state(300, 320, 40)])
        self.assertIsNotNone(first)
        selector.update([])
        selector.update([])
        self.assertIsNone(selector.update([]))
        replacement = selector.update([state(500, 320, 40)])
        self.assertIsNotNone(replacement)
        self.assertNotEqual(replacement.track_id, first.track_id)

    def test_lab_modulation_is_reproducible_and_converges(self) -> None:
        a = generate(
            "bezier", 160.0, -80.0, steps=20, seed=7,
            lab_modulation=True, noise_scale=0.8,
            overshoot_probability=1.0, modulation_seed=11,
        )
        b = generate(
            "bezier", 160.0, -80.0, steps=20, seed=7,
            lab_modulation=True, noise_scale=0.8,
            overshoot_probability=1.0, modulation_seed=11,
        )
        self.assertTrue(np.array_equal(np.asarray(a.points), np.asarray(b.points)))
        self.assertEqual(a.points[-1], (160.0, -80.0))
        self.assertEqual(a.extras["lab_modulation"], 1.0)


if __name__ == "__main__":
    unittest.main()
