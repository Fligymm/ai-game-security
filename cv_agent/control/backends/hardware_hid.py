"""Protocol-only HID backend extension point."""

from __future__ import annotations

import struct
from collections.abc import Callable

from cv_agent.control.base import BaseMouseBackend


class HardwareHIDBackend(BaseMouseBackend):
    """Format packets without opening devices or invoking platform APIs."""

    MAGIC = b"MH"

    def __init__(self, *, mock: bool = True, custom_writer: Callable[[bytes], None] | None = None) -> None:
        self.mock = bool(mock)
        self.custom_writer = custom_writer
        self.mock_packets: list[bytes] = []

    @property
    def supports_real_output(self) -> bool:
        return not self.mock and self.custom_writer is not None

    def send_relative_move(self, dx: int, dy: int) -> None:
        packet = self.format_packet(dx, dy)
        if self.mock:
            self.mock_packets.append(packet)
            return
        if self.custom_writer is None:
            raise RuntimeError(
                "HardwareHIDBackend is in real mode but no custom_writer was injected; "
                "use mock=True or an explicit writer"
            )
        self.custom_writer(packet)

    def log_relative_move(self, dx: int, dy: int) -> None:
        """Record a mock packet; never call a real HID writer."""

        if self.supports_real_output:
            return
        self.send_relative_move(dx, dy)

    @classmethod
    def format_packet(cls, dx: int, dy: int) -> bytes:
        dx = max(-32768, min(32767, int(dx)))
        dy = max(-32768, min(32767, int(dy)))
        body = struct.pack("<Bhh", 1, dx, dy)
        return cls.MAGIC + body + bytes([sum(body) & 0xFF])

    def reset(self) -> None:
        self.mock_packets.clear()
