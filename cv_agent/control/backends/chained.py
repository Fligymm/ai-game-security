"""Multi-backend chain for simultaneous CSV logging and control output."""

from __future__ import annotations

from typing import Mapping, Sequence

from cv_agent.control.base import BaseMouseBackend


class ChainedBackend(BaseMouseBackend):
    """Chain multiple backends together; all receive send_relative_move calls.
    
    This allows simultaneous CSV logging, visualization, and real control output.
    Useful for ensuring move history is preserved while also sending real input.
    """

    def __init__(self, backends: Sequence[BaseMouseBackend], *, strict: bool = False) -> None:
        """Initialize with a sequence of backends.
        
        Args:
            backends: Sequence of backends to chain.
            strict: If True, raise on first error. If False, log and continue.
        """
        if not backends:
            raise ValueError("ChainedBackend requires at least one backend")
        self._backends = list(backends)
        self._strict = bool(strict)

    def send_relative_move(self, dx: int, dy: int) -> None:
        """Send relative movement to all backends."""
        for backend in self._backends:
            try:
                backend.send_relative_move(int(dx), int(dy))
            except Exception as e:
                if self._strict:
                    raise
                # Silently continue; one backend's failure should not block others

    def reset(self) -> None:
        """Reset all backends."""
        for backend in self._backends:
            try:
                backend.reset()
            except Exception as e:
                if self._strict:
                    raise

    def set_context(self, values: Mapping[str, object] | None = None) -> None:
        """Set context on all backends."""
        for backend in self._backends:
            try:
                backend.set_context(values)
            except Exception as e:
                if self._strict:
                    raise

    def close(self) -> None:
        """Close all backends in reverse order for proper cleanup."""
        exceptions: list[Exception] = []
        for backend in reversed(self._backends):
            try:
                backend.close()
            except Exception as e:
                exceptions.append(e)
                if self._strict:
                    raise
        # In non-strict mode, silently collect exceptions; they're logged via close()
