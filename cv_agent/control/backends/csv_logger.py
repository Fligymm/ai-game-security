"""CSV movement logger for offline analysis."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Mapping

from cv_agent.control.base import BaseMouseBackend


class CSVLoggerBackend(BaseMouseBackend):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
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
        self._handle.close()
