"""OpenCV canvas backend for virtual cursor-path rendering."""

from __future__ import annotations

import cv2
import numpy as np

from cv_agent.control.base import BaseMouseBackend


class CanvasVisualizerBackend(BaseMouseBackend):
    def __init__(self, *, width: int = 800, height: int = 600, window_name: str = "Virtual Mouse") -> None:
        self.width = int(width)
        self.height = int(height)
        self.window_name = window_name
        self.canvas = np.full((self.height, self.width, 3), 24, dtype=np.uint8)
        self.position = np.array([self.width // 2, self.height // 2], dtype=np.float64)

    def send_relative_move(self, dx: int, dy: int) -> None:
        previous = self.position.copy()
        self.position += (int(dx), int(dy))
        self.position[0] = np.clip(self.position[0], 0, self.width - 1)
        self.position[1] = np.clip(self.position[1], 0, self.height - 1)
        cv2.line(self.canvas, tuple(previous.astype(int)), tuple(self.position.astype(int)), (0, 210, 255), 2)
        cv2.circle(self.canvas, tuple(self.position.astype(int)), 5, (40, 240, 80), -1)
        cv2.imshow(self.window_name, self.canvas)
        cv2.waitKey(1)

    def reset(self) -> None:
        self.canvas.fill(24)
        self.position[:] = (self.width // 2, self.height // 2)

    def close(self) -> None:
        cv2.destroyWindow(self.window_name)
