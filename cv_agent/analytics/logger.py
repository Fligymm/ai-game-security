"""Persistence for offline trajectory sessions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from uuid import uuid4

from .trajectory_schema import EventSegment, TrajectorySession, TrajectorySource


class TrajectoryLogger:
    """Collect relative movements and persist one validated session."""

    def __init__(
        self,
        *,
        session_id: str | None = None,
        source: TrajectorySource,
        target_distance_px: float,
        target_size_px: float,
        reaction_time_ms: float,
        seed: int | None = None,
        start_time: float | None = None,
    ) -> None:
        self.session_id = session_id or uuid4().hex
        self.source = source
        self.target_distance_px = float(target_distance_px)
        self.target_size_px = float(target_size_px)
        self.reaction_time_ms = float(reaction_time_ms)
        self.seed = seed
        self.start_time = time.monotonic() if start_time is None else float(start_time)
        self._timestamps: list[float] = []
        self._x: list[float] = []
        self._y: list[float] = []
        self._dx: list[int] = []
        self._dy: list[int] = []
        self._segments: list[EventSegment] = []

    def add_frame(
        self,
        dx: int,
        dy: int,
        *,
        timestamp: float | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> None:
        """Append one relative move; timestamp is seconds from session start."""
        dx_i, dy_i = int(dx), int(dy)
        if dx_i != dx or dy_i != dy:
            raise TypeError("dx and dy must be integers")
        timestamp_s = time.monotonic() - self.start_time if timestamp is None else float(timestamp)
        if self._timestamps and timestamp_s <= self._timestamps[-1]:
            raise ValueError("timestamp must be strictly greater than the previous timestamp")
        previous_x = self._x[-1] if self._x else 0.0
        previous_y = self._y[-1] if self._y else 0.0
        self._timestamps.append(timestamp_s)
        self._dx.append(dx_i)
        self._dy.append(dy_i)
        self._x.append(previous_x + dx_i if x is None else float(x))
        self._y.append(previous_y + dy_i if y is None else float(y))

    def append_point(self, timestamp: float, x: float, y: float, dx: int, dy: int) -> None:
        """Append a fully specified point using the public schema order."""
        self.add_frame(dx, dy, timestamp=timestamp, x=x, y=y)

    def add_event(self, phase: str, start_idx: int, end_idx: int) -> None:
        self._segments.append(EventSegment(phase, int(start_idx), int(end_idx)))

    def build(self) -> TrajectorySession:
        return TrajectorySession(
            session_id=self.session_id,
            source=self.source,
            target_distance_px=self.target_distance_px,
            target_size_px=self.target_size_px,
            reaction_time_ms=self.reaction_time_ms,
            timestamps=list(self._timestamps),
            x=list(self._x),
            y=list(self._y),
            dx=list(self._dx),
            dy=list(self._dy),
            event_segments=list(self._segments),
            seed=self.seed,
        )

    def save_json(self, path: str | Path) -> Path:
        output = Path(path)
        os.makedirs(os.path.dirname(os.fspath(output)) or ".", exist_ok=True)
        output.write_text(json.dumps(self.build().to_dict(), indent=2), encoding="utf-8")
        return output

    def export_to_json(self, path: str | Path) -> Path:
        """Compatibility alias for the simple export API."""
        return self.save_json(path)

    @property
    def frame_count(self) -> int:
        """Number of points collected so far."""
        return len(self._timestamps)

    def save_parquet(self, path: str | Path) -> Path:
        """Write one row per frame and repeat session metadata on each row."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("Parquet export requires pandas and pyarrow") from exc
        session = self.build()
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "session_id": session.session_id,
                "source": session.source,
                "target_distance_px": session.target_distance_px,
                "target_size_px": session.target_size_px,
                "reaction_time_ms": session.reaction_time_ms,
                "seed": session.seed,
                "timestamp_s": timestamp,
                "x": x,
                "y": y,
                "dx": dx,
                "dy": dy,
            }
            for timestamp, x, y, dx, dy in zip(session.timestamps, session.x, session.y, session.dx, session.dy)
        ]
        try:
            pd.DataFrame(rows).to_parquet(output, index=False)
        except ImportError as exc:
            raise RuntimeError("Parquet export requires a parquet engine such as pyarrow") from exc
        return output
