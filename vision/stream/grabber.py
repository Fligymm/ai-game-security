"""Low-latency screen capture with BetterCam-first, mss fallback behavior.

The grabber exposes a small lifecycle-oriented API that returns BGR numpy
frames ready for vision.detection consumers. It keeps track of the ROI offset
inside the selected display so downstream code can map detections back to the
full-screen coordinate system.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class ScreenRegion:
    """Absolute capture rectangle on the selected monitor."""

    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def box(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.right, self.bottom


class ScreenGrabber:
    """Capture a centered ROI from the desktop with a single interface.

    Parameters
    ----------
    roi_width, roi_height:
        Size of the captured region. Defaults to the YOLO training resolution.
    target_fps:
        Requested capture rate for BetterCam. The actual rate depends on the
        system and display mode.
    monitor_index:
        Primary monitor by default. This follows the mss monitor numbering
        convention where 1 is the first physical display.
    prefer_bettercam:
        Try BetterCam first on Windows; fall back to mss when unavailable.
    fallback_to_mss:
        Allow mss capture when BetterCam cannot be created or started.
    """

    def __init__(
        self,
        *,
        roi_width: int = 640,
        roi_height: int = 640,
        target_fps: int = 144,
        monitor_index: int = 1,
        prefer_bettercam: bool = True,
        fallback_to_mss: bool = True,
    ) -> None:
        if roi_width <= 0 or roi_height <= 0:
            raise ValueError("roi_width and roi_height must be positive")
        if target_fps <= 0:
            raise ValueError("target_fps must be positive")
        if monitor_index < 1:
            raise ValueError("monitor_index must be >= 1")

        self.roi_width = int(roi_width)
        self.roi_height = int(roi_height)
        self.target_fps = int(target_fps)
        self.monitor_index = int(monitor_index)
        self.prefer_bettercam = bool(prefer_bettercam)
        self.fallback_to_mss = bool(fallback_to_mss)

        self.backend: str | None = None
        self.offset_x: int = 0
        self.offset_y: int = 0
        self.screen_left: int = 0
        self.screen_top: int = 0
        self.screen_width: int = 0
        self.screen_height: int = 0

        self._capture: Any = None
        self._mss = None
        self._region: ScreenRegion | None = None
        self._running = False

    def __enter__(self) -> ScreenGrabber:
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    @property
    def roi_box(self) -> tuple[int, int, int, int]:
        """Absolute ROI bounds as (left, top, right, bottom)."""

        if self._region is None:
            self._resolve_geometry()
        assert self._region is not None
        return self._region.box

    @property
    def frame_shape(self) -> tuple[int, int, int]:
        """Expected frame shape for the ROI output."""

        return self.roi_height, self.roi_width, 3

    def start(self) -> ScreenGrabber:
        """Start the capture backend if needed."""

        if self._running:
            return self

        self._resolve_geometry()
        if self.prefer_bettercam and sys.platform == "win32":
            try:
                self._start_bettercam()
                self.backend = "bettercam"
                self._running = True
                return self
            except Exception as exc:
                if not self.fallback_to_mss:
                    raise RuntimeError(
                        "BetterCam initialization failed and fallback_to_mss is disabled: "
                        f"{exc}"
                    ) from exc
                print(
                    "[ScreenGrabber] BetterCam unavailable, falling back to mss: "
                    f"{exc}",
                    file=sys.stderr,
                )

        self._start_mss()
        self.backend = "mss"
        self._running = True
        return self

    def stop(self) -> None:
        """Stop and release the active backend."""

        if not self._running:
            return

        if self._capture is not None:
            if self.backend == "bettercam":
                stop = getattr(self._capture, "stop", None)
                if callable(stop):
                    stop()
            self._capture = None

        if self._mss is not None:
            close = getattr(self._mss, "close", None)
            if callable(close):
                close()
            self._mss = None

        self._running = False

    def get_frame(self) -> np.ndarray:
        """Return one BGR frame from the configured ROI."""

        if not self._running:
            self.start()

        if self.backend == "bettercam":
            frame = self._capture.get_latest_frame() if self._capture is not None else None
            if frame is None:
                frame = self._capture.grab() if self._capture is not None else None
        elif self.backend == "mss":
            frame = self._grab_mss_frame()
        else:
            raise RuntimeError("ScreenGrabber is not started")

        if frame is None:
            raise RuntimeError(f"{self.backend or 'screen'} capture returned no frame")

        frame = self._ensure_bgr(frame)
        if frame.shape[:2] != (self.roi_height, self.roi_width):
            frame = cv2.resize(frame, (self.roi_width, self.roi_height), interpolation=cv2.INTER_LINEAR)
        return frame

    def get_latest_frame(self) -> np.ndarray:
        """Alias for get_frame() to match typical live-capture APIs."""

        return self.get_frame()

    def _resolve_geometry(self) -> ScreenRegion:
        if self._region is not None:
            return self._region

        mss_module = self._import_mss()
        with mss_module.mss() as sct:
            monitors = getattr(sct, "monitors", None)
            if not monitors or len(monitors) <= self.monitor_index:
                raise RuntimeError(
                    f"Unable to resolve monitor {self.monitor_index}; available: {max(len(monitors) - 1, 0) if monitors else 0}"
                )
            monitor = monitors[self.monitor_index]

        self.screen_left = int(monitor["left"])
        self.screen_top = int(monitor["top"])
        self.screen_width = int(monitor["width"])
        self.screen_height = int(monitor["height"])

        roi_width = min(self.roi_width, self.screen_width)
        roi_height = min(self.roi_height, self.screen_height)
        self.roi_width = roi_width
        self.roi_height = roi_height
        self.offset_x = max(0, (self.screen_width - roi_width) // 2)
        self.offset_y = max(0, (self.screen_height - roi_height) // 2)

        self._region = ScreenRegion(
            left=self.screen_left + self.offset_x,
            top=self.screen_top + self.offset_y,
            width=roi_width,
            height=roi_height,
        )
        return self._region

    def _start_bettercam(self) -> None:
        bettercam = self._import_bettercam()
        region = self._resolve_geometry()
        output_idx = max(self.monitor_index - 1, 0)

        create_attempts = [
            {"output_idx": output_idx, "output_color": "BGR", "region": region.box},
            {"output_idx": output_idx, "output_color": "BGR", "region": (region.left, region.top, region.width, region.height)},
            {"output_idx": output_idx, "output_color": "BGR"},
            {"output_idx": output_idx},
            {"output_color": "BGR", "region": region.box},
            {"output_color": "BGR", "region": (region.left, region.top, region.width, region.height)},
            {},
        ]
        last_error: Exception | None = None
        for kwargs in create_attempts:
            try:
                self._capture = bettercam.create(**kwargs)
                break
            except Exception as exc:  # pragma: no cover - backend-specific behavior
                last_error = exc
                self._capture = None
        if self._capture is None:
            raise RuntimeError("bettercam.create failed") from last_error

        start_attempts = [
            {"target_fps": self.target_fps, "video_mode": True},
            {"target_fps": self.target_fps},
            {"fps": self.target_fps, "video_mode": True},
            {"fps": self.target_fps},
            {},
        ]
        last_error = None
        for kwargs in start_attempts:
            try:
                start = getattr(self._capture, "start", None)
                if callable(start):
                    start(**kwargs)
                    return
                break
            except Exception as exc:  # pragma: no cover - backend-specific behavior
                last_error = exc
        if last_error is not None:
            raise RuntimeError("bettercam.start failed") from last_error

    def _start_mss(self) -> None:
        self._mss = self._import_mss().mss()
        self._capture = self._mss

    def _grab_mss_frame(self) -> np.ndarray:
        if self._mss is None:
            raise RuntimeError("mss backend is not initialized")
        assert self._region is not None
        frame = self._mss.grab({"left": self._region.left, "top": self._region.top, "width": self._region.width, "height": self._region.height})
        return cv2.cvtColor(np.asarray(frame), cv2.COLOR_BGRA2BGR)

    @staticmethod
    def _ensure_bgr(frame: np.ndarray) -> np.ndarray:
        if not isinstance(frame, np.ndarray):
            frame = np.asarray(frame)
        if frame.ndim == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if frame.ndim == 3 and frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        if frame.ndim == 3 and frame.shape[2] == 3:
            return frame
        raise ValueError(f"Unsupported frame shape: {getattr(frame, 'shape', None)}")

    @staticmethod
    def _import_bettercam() -> Any:
        if sys.platform != "win32":
            raise RuntimeError("BetterCam is only available on Windows")
        try:
            import bettercam
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "bettercam is not installed. Install with: pip install bettercam"
            ) from exc
        return bettercam

    @staticmethod
    def _import_mss() -> Any:
        try:
            import mss
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "mss is not installed. Install with: pip install mss"
            ) from exc
        return mss


if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser(description="Preview ROI capture using ScreenGrabber")
    parser.add_argument("--roi-width", type=int, default=640)
    parser.add_argument("--roi-height", type=int, default=640)
    parser.add_argument("--fps", type=int, default=144)
    parser.add_argument("--monitor-index", type=int, default=1)
    args = parser.parse_args()

    with ScreenGrabber(
        roi_width=args.roi_width,
        roi_height=args.roi_height,
        target_fps=args.fps,
        monitor_index=args.monitor_index,
    ) as grabber:
        print(
            f"backend={grabber.backend} roi=({grabber.roi_width}x{grabber.roi_height}) "
            f"offset=({grabber.offset_x}, {grabber.offset_y}) screen=({grabber.screen_width}x{grabber.screen_height})"
        )
        window_name = "ScreenGrabber ROI Preview"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, grabber.roi_width, grabber.roi_height)
        try:
            while True:
                frame = grabber.get_latest_frame()
                center_x = grabber.screen_width // 2 - grabber.offset_x
                center_y = grabber.screen_height // 2 - grabber.offset_y
                if 0 <= center_x < frame.shape[1] and 0 <= center_y < frame.shape[0]:
                    cv2.circle(frame, (center_x, center_y), 6, (0, 0, 255), -1)
                cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1), (255, 255, 255), 1)
                cv2.putText(
                    frame,
                    f"backend={grabber.backend} offset=({grabber.offset_x},{grabber.offset_y})",
                    (12, 24),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                time.sleep(0.001)
        finally:
            cv2.destroyAllWindows()
