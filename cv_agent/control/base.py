"""Backend-neutral control output interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping


class BaseMouseBackend(ABC):
    """Strategy interface for relative movement sinks."""

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
