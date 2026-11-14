"""Win32-named, platform-neutral callback backend.

The class name is retained for configuration compatibility. This module has
no ctypes, user32, or other platform input dependencies.
"""

from __future__ import annotations

from collections.abc import Callable

from cv_agent.control.base import BaseMouseBackend


class Win32APIBackend(BaseMouseBackend):
    """Dry-run movement sink with an optional explicitly injected callback."""

    def __init__(self, *, dry_run: bool = True, custom_handler: Callable[[int, int], None] | None = None) -> None:
        self.dry_run = bool(dry_run)
        self.custom_handler = custom_handler
        self.moves: list[tuple[int, int]] = []

    @property
    def supports_real_output(self) -> bool:
        return not self.dry_run and self.custom_handler is not None

    def send_relative_move(self, dx: int, dy: int) -> None:
        dx = max(-32768, min(32767, int(dx)))
        dy = max(-32768, min(32767, int(dy)))
        if self.dry_run:
            self.moves.append((dx, dy))
            return
        if self.custom_handler is None:
            raise RuntimeError(
                "Win32APIBackend is in real mode but no custom_handler was injected; "
                "use dry_run=True or the run_real.py hook"
            )
        self.custom_handler(dx, dy)

    def reset(self) -> None:
        self.moves.clear()
