"""Central factory for safe control-output strategies."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cv_agent.control import (
    BaseMouseBackend,
    CSVLoggerBackend,
    CanvasVisualizerBackend,
    HardwareHIDBackend,
    Win32APIBackend,
)


def create_mouse_backend(
    name: str = "csv",
    *,
    output_path: str | Path = "runs/predict/control_moves.csv",
    allow_external_handler: bool = False,
    custom_handler: Callable[[int, int], None] | None = None,
    custom_writer: Callable[[bytes], None] | None = None,
) -> BaseMouseBackend:
    """Create a backend; external callbacks require an explicit opt-in flag."""
    if (custom_handler is not None or custom_writer is not None) and not allow_external_handler:
        raise PermissionError("external handlers require allow_external_handler=True")
    key = name.lower().strip()
    if key == "csv":
        return CSVLoggerBackend(output_path)
    if key == "canvas":
        return CanvasVisualizerBackend()
    if key == "win32":
        return Win32APIBackend(dry_run=True, custom_handler=custom_handler)
    if key == "hid":
        return HardwareHIDBackend(mock=True, custom_writer=custom_writer)
    raise ValueError(f"unknown backend '{name}', expected csv, canvas, win32, or hid")
