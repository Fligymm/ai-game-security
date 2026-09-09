"""CSV movement logger for offline analysis."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Mapping

from cv_agent.control.base import BaseMouseBackend


class CSVLoggerBackend(BaseMouseBackend):
    def __init__(self, path: str | Path | None = None, *, filepath: str | Path | None = None) -> None:
        if path is not None and filepath is not None:
            raise TypeError("specify either path or filepath, not both")
        selected = filepath if filepath is not None else path
        if selected is None:
            selected = Path("runs/predict") / f"control_moves_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        self.path = Path(selected)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._handle)
        self._writer.writerow(["timestamp_ns", "dx", "dy", "metadata"])
        self._context: dict[str, object] = {}

    def set_context(self, values: Mapping[str, object] | None = None) -> None:
        self._context = dict(values or {})

    def send_relative_move(self, dx: int, dy: int) -> None:
        self._writer.writerow([time.time_ns(), int(dx), int(dy), repr(self._context)])
        self._handle.flush()

    def reset(self) -> None:
        self._context = {}

    def close(self) -> None:
        if getattr(self, "_handle", None) is None or self._handle.closed:
            return
        try:
            self._handle.flush()
        finally:
            try:
                self._handle.close()
            except OSError:
                pass

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
