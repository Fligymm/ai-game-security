from __future__ import annotations

from tools.extract_p0c_features import frame_rows, summarize_session


def _record(index: int, *, selected: bool, track: int | None = None, offset=None, cls: int = 1):
    det = {"x1": 0, "y1": 0, "x2": 10, "y2": 10, "confidence": 0.8, "class_id": cls, "track_id": track}
    return {
        "frame_index": index,
        "video_time_s": index / 30.0,
        "capture_time_s": index / 30.0,
        "detections": [det] if selected else [],
        "selected": (
            {
                "x1": 0, "y1": 0, "x2": 10, "y2": 10,
                "confidence": 0.8, "class_id": cls,
                "class_name": "enemy_body" if cls == 1 else "enemy_head",
                "track_id": track, "delta_x": 1.0, "delta_y": 1.0,
            }
            if selected else None
        ),
        "compensated_offset": offset if selected else None,
        "applied_mouse": False,
    }


def test_frame_features_and_episodes() -> None:
    records = [
        _record(0, selected=True, track=1, offset=[3.0, 4.0]),
        _record(1, selected=True, track=1, offset=[6.0, 8.0]),
        _record(2, selected=False),
        _record(3, selected=True, track=2, offset=[0.0, 5.0], cls=0),
    ]
    rows = frame_rows(records)
    assert [row["selected"] for row in rows] == [True, True, False, True]
    assert rows[3]["track_switched"] is True
    assert rows[0]["offset_px"] == 5.0
    meta = {"source_session_id": "x", "source_agent_type": "human", "dry_run": True}
    summary = summarize_session(meta, rows)
    assert summary["frames"] == 4
    assert summary["selected_frames"] == 3
    assert summary["acquisition_episodes"] == 2
    assert summary["selected_class_counts"]["enemy_head"] == 1
    assert summary["all_applied_false"] is True