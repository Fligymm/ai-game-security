"""Central factory for safe control-output strategies."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cv_agent.control import (
    BaseMouseBackend,
    CSVLoggerBackend,
    CanvasVisualizerBackend,
    ChainedBackend,
    HardwareHIDBackend,
    Win32APIBackend,
)


def create_mouse_backend(
    name: str = "csv",
    *,
    output_path: str | Path | None = None,
    allow_external_handler: bool = False,
    custom_handler: Callable[[int, int], None] | None = None,
    custom_writer: Callable[[bytes], None] | None = None,
    always_include_csv: bool = True,
) -> BaseMouseBackend:
    """Create a backend; external callbacks require an explicit opt-in flag.
    
    Args:
        name: Backend type ("csv", "canvas", "win32", "hid").
        output_path: CSV output path (defaults to timestamped runs/predict file).
        allow_external_handler: Permit custom_handler/custom_writer injection.
        custom_handler: Custom Win32 movement callback (requires allow_external_handler=True).
        custom_writer: Custom HID output callback (requires allow_external_handler=True).
        always_include_csv: Chain CSV logger with other backends for dual recording+control.
            If True and name != "csv", returns ChainedBackend([CSVLoggerBackend, ...]). 
            If False or name=="csv", returns only the requested backend.
    
    Returns:
        A backend configured for the specified mode.
    """
    if (custom_handler is not None or custom_writer is not None) and not allow_external_handler:
        raise PermissionError("external handlers require allow_external_handler=True")
    
    key = name.lower().strip()
    
    # Create the primary backend based on name
    if key == "csv":
        return CSVLoggerBackend(output_path)
    
    # For non-CSV backends, optionally chain with CSV logger
    primary_backend: BaseMouseBackend
    if key == "canvas":
        primary_backend = CanvasVisualizerBackend()
    elif key == "win32":
        primary_backend = Win32APIBackend(dry_run=True, custom_handler=custom_handler)
    elif key == "hid":
        primary_backend = HardwareHIDBackend(mock=True, custom_writer=custom_writer)
    else:
        raise ValueError(f"unknown backend '{name}', expected csv, canvas, win32, or hid")
    
    # Chain with CSV logging if enabled (and not already CSV backend)
    if always_include_csv and key != "csv":
        csv_backend = CSVLoggerBackend(output_path)
        return ChainedBackend([csv_backend, primary_backend])
    
    return primary_backend
