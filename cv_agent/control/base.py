"""Backend-neutral control output interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping


class BaseMouseBackend(ABC):
    """Strategy interface for relative movement sinks."""

    @property
    def supports_real_output(self) -> bool:
        """Whether this backend can actually control a real input device.

        Recording/visualisation backends must return False.  This is used by
        the realtime loop to keep ``applied_mouse`` honest and to avoid
        reporting a CSV write as a real input event.
        """

        return False

    @abstractmethod
    def send_relative_move(self, dx: int, dy: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError

    def set_context(self, values: Mapping[str, object] | None = None) -> None:
        pass

    def close(self) -> None:
        pass
