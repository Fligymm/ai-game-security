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

    def send_relative_move(self, dx: int, dy: int) -> None:
        packet = self.format_packet(dx, dy)
        if self.custom_writer is not None:
            self.custom_writer(packet)
        else:
            self.mock_packets.append(packet)

    @classmethod
    def format_packet(cls, dx: int, dy: int) -> bytes:
        dx = max(-32768, min(32767, int(dx)))
        dy = max(-32768, min(32767, int(dy)))
        body = struct.pack("<Bhh", 1, dx, dy)
        return cls.MAGIC + body + bytes([sum(body) & 0xFF])

    def reset(self) -> None:
        self.mock_packets.clear()
