from __future__ import annotations

import json
import random

from tools.sample_annotation import choose_even, select_sessions


def test_choose_even_spreads_across_timeline() -> None:
    items = [{"frame_id": index} for index in range(100)]
    picked = choose_even(items, 10, random.Random(7))
    assert len(picked) == 10
    ids = [item["frame_id"] for item in picked]
    assert ids == sorted(ids)
    assert len(set(ids)) == 10


def test_select_sessions_picks_latest_per_scene(tmp_path) -> None:
    captures = tmp_path / "captures"
    for name, scene, started in (
        ("old_static", "static_target", 1),
        ("new_static", "static_target", 3),
        ("slow", "slow_strafe", 2),
        ("ignored", "other", 9),
    ):
        session_dir = captures / name
        session_dir.mkdir(parents=True)
        (session_dir / "session.json").write_text(
            json.dumps(
                {
                    "session_id": name,
                    "scene": scene,
                    "started_at_wall_ns": started,
                }
            ),
            encoding="utf-8",
        )

    selected = select_sessions(tmp_path, ("static_target", "slow_strafe"))
    assert [path.name for path in selected] == ["new_static", "slow"]