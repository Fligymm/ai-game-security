"""Fail-closed Windows client-area capture for a specific game window.

The existing ``ScreenGrabber`` captures a centered monitor ROI. P0-B needs to
record a named game window, reject minimized/unfocused windows, and never fall
back to the desktop when the game is missing. This module provides that minimal
window-specific capture path.

Limitations:
- Windows only.
- Captures the window's client area via desktop composition (mss). It requires
  the target window to be visible and foreground; occluded/background content is
  rejected rather than guessed.
- Exclusive fullscreen, HDR, and protected content may not be captured; the
  caller must treat capture failures as invalid data, not as a desktop fallback.
"""

from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass

import cv2
import numpy as np


class GameWindowError(RuntimeError):
    """The requested game window does not exist or is not uniquely identifiable."""


class WindowCaptureError(RuntimeError):
    """The game window became invalid during capture."""


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """Snapshot of a Windows game window's client area."""

    hwnd: int
    title: str
    class_name: str
    client_left: int
    client_top: int
    width: int
    height: int
    is_visible: bool
    is_minimized: bool
    is_foreground: bool
    pid: int = 0
    process_name: str = ""
    exe_path: str = ""


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _window_text(hwnd: int) -> str:
    length = int(ctypes.windll.user32.GetWindowTextLengthW(hwnd))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _process_info(hwnd: int) -> tuple[int, str, str]:
    """Return (pid, process_name, full_exe_path) for a window, if accessible."""

    pid = wintypes.DWORD(0)
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return 0, "", ""

    kernel32 = ctypes.windll.kernel32
    # PROCESS_QUERY_LIMITED_INFORMATION; avoids requiring full access rights.
    handle = kernel32.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return int(pid.value), "", ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(size)
        )
        path = buffer.value if ok else ""
        return int(pid.value), os.path.basename(path), path
    finally:
        kernel32.CloseHandle(handle)


def _cs2_window(info: WindowInfo) -> bool:
    """True when the window belongs to cs2.exe or uses a known CS2 title."""

    if info.process_name.lower() == "cs2.exe":
        return True
    path = info.exe_path.lower().replace("/", "\\")
    if path.endswith("\\cs2.exe"):
        return True
    title = info.title.lower()
    aliases = (
        "counter-strike 2",
        "counter-strike: global offensive",
        "counter-strike global offensive",
        "反恐精英",
        "cs2",
    )
    return any(alias in title for alias in aliases)


def window_info(hwnd: int) -> WindowInfo:
    """Read a window's client geometry and state. Raises for invalid handles."""

    if sys.platform != "win32":
        raise GameWindowError("window capture is only supported on Windows")
    user32 = ctypes.windll.user32
    if not user32.IsWindow(hwnd):
        raise GameWindowError(f"window handle is not valid: {hwnd}")

    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise GameWindowError(f"GetClientRect failed for hwnd={hwnd}")
    origin = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        raise GameWindowError(f"ClientToScreen failed for hwnd={hwnd}")

    pid, process_name, exe_path = _process_info(hwnd)
    return WindowInfo(
        hwnd=int(hwnd),
        title=_window_text(hwnd),
        class_name=_class_name(hwnd),
        client_left=int(origin.x),
        client_top=int(origin.y),
        width=int(rect.right - rect.left),
        height=int(rect.bottom - rect.top),
        is_visible=bool(user32.IsWindowVisible(hwnd)),
        is_minimized=bool(user32.IsIconic(hwnd)),
        is_foreground=bool(user32.GetForegroundWindow() == hwnd),
        pid=pid,
        process_name=process_name,
        exe_path=exe_path,
    )


def _visible_windows() -> list[int]:
    if sys.platform != "win32":
        raise GameWindowError("window discovery is only supported on Windows")
    user32 = ctypes.windll.user32
    matches: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            matches.append(int(hwnd))
        return True

    user32.EnumWindows(_enum, 0)
    return matches


def find_game_window(title_contains: str | None = None) -> WindowInfo:
    """Find the visible CS2 window.

    Default detection uses the process image (``cs2.exe``), not the localized
    window title. A title override remains available for unusual launchers, but
    the default works with Chinese/English/Steam-localized CS2 titles.
    """

    if sys.platform != "win32":
        raise GameWindowError("window discovery is only supported on Windows")
    if title_contains is not None and not title_contains.strip():
        raise GameWindowError("title_contains must not be empty when supplied")

    candidates = [window_info(hwnd) for hwnd in _visible_windows()]
    if title_contains is not None:
        needle = title_contains.lower()
        titled = [info for info in candidates if needle in info.title.lower()]
        if len(titled) > 1:
            titles = [f"{info.hwnd}: {info.title}" for info in titled]
            raise GameWindowError(
                "multiple windows match; refuse ambiguous capture: " + "; ".join(titles)
            )
        if titled:
            return titled[0]
        # Compatibility: an English title override must not fail on a localized
        # CS2 title. Fall through to process-based discovery when cs2.exe exists.
        # If no cs2.exe exists, report the original title error below.

    cs2 = [info for info in candidates if _cs2_window(info)]
    if not cs2 and title_contains is not None:
        raise GameWindowError(f"no visible window title contains {title_contains!r}")
    if not cs2:
        titles = [f"{info.hwnd}: {info.title!r}" for info in candidates if info.title]
        raise GameWindowError(
            "no visible CS2 window found (cs2.exe); visible titles: "
            + "; ".join(titles[:8])
        )

    # A cs2.exe process can own hidden/overlay/helper windows. Select the main
    # visible game window deterministically: foreground first, then client area.
    cs2.sort(
        key=lambda info: (
            bool(info.is_foreground),
            int(info.width) * int(info.height),
            info.class_name == "SDL_app",
        ),
        reverse=True,
    )
    return cs2[0]


def focus_game_window(hwnd: int) -> None:
    """Bring a game window to the foreground; fail if Windows refuses."""

    if sys.platform != "win32":
        raise GameWindowError("window focus is only supported on Windows")
    user32 = ctypes.windll.user32
    if not user32.IsWindow(hwnd):
        raise GameWindowError(f"window handle is not valid: {hwnd}")
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    for _ in range(20):
        if user32.GetForegroundWindow() == hwnd:
            return
        time.sleep(0.05)
    raise GameWindowError(
        "could not bring the game window to the foreground; click the CS2 window "
        "once and rerun (Windows may block background focus changes)"
    )


def validate_window_state(info: WindowInfo, *, require_foreground: bool = True) -> list[str]:
    """Return human-readable reasons why a window snapshot is not capturable."""

    errors: list[str] = []
    if not info.is_visible:
        errors.append("game window is not visible")
    if info.is_minimized:
        errors.append("game window is minimized")
    if info.width <= 0 or info.height <= 0:
        errors.append("game window client area is empty")
    if require_foreground and not info.is_foreground:
        errors.append("game window is not foreground; refusing to capture desktop/occluded content")
    return errors


class WindowCapture:
    """Capture a specific game window's client area at a target rate."""

    def __init__(
        self,
        *,
        title_contains: str | None = None,
        target_fps: int = 60,
        require_foreground: bool = True,
        focus: bool = False,
    ) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be positive")
        self.title_contains = title_contains
        self.target_fps = int(target_fps)
        self.require_foreground = bool(require_foreground)
        self.focus = bool(focus)
        self._mss = None
        self._window: WindowInfo | None = None
        self.last_frame_timestamp_ns: int | None = None

    @property
    def window(self) -> WindowInfo:
        if self._window is None:
            raise WindowCaptureError("WindowCapture is not started")
        return self._window

    @property
    def frame_shape(self) -> tuple[int, int, int]:
        return self.window.height, self.window.width, 3

    def __enter__(self) -> "WindowCapture":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> "WindowCapture":
        if self._mss is not None:
            return self
        if sys.platform != "win32":
            raise GameWindowError("window capture is only supported on Windows")
        _enable_dpi_awareness()
        info = find_game_window(self.title_contains)
        if self.require_foreground and not info.is_foreground and self.focus:
            focus_game_window(info.hwnd)
            info = window_info(info.hwnd)
        errors = validate_window_state(info, require_foreground=self.require_foreground)
        if errors:
            raise WindowCaptureError("; ".join(errors))
        try:
            import mss
        except ImportError as exc:  # pragma: no cover - dependency installed in repo
            raise RuntimeError("mss is required for window capture") from exc
        self._mss = mss.mss()
        self._window = info
        return self

    def stop(self) -> None:
        if self._mss is not None:
            close = getattr(self._mss, "close", None)
            if callable(close):
                close()
            self._mss = None
        self._window = None

    def _refresh(self) -> WindowInfo:
        if self._window is None:
            raise WindowCaptureError("WindowCapture is not started")
        try:
            info = window_info(self._window.hwnd)
        except GameWindowError as exc:
            raise WindowCaptureError(f"game window disappeared: {exc}") from exc
        if (info.width, info.height) != (self._window.width, self._window.height):
            raise WindowCaptureError(
                "game window client size changed "
                f"{self._window.width}x{self._window.height} -> {info.width}x{info.height}"
            )
        errors = validate_window_state(info, require_foreground=self.require_foreground)
        if errors:
            raise WindowCaptureError("; ".join(errors))
        self._window = info
        return info

    def get_frame(self) -> np.ndarray:
        if self._mss is None:
            self.start()
        assert self._mss is not None
        info = self._refresh()
        try:
            shot = self._mss.grab(
                {
                    "left": info.client_left,
                    "top": info.client_top,
                    "width": info.width,
                    "height": info.height,
                }
            )
        except Exception as exc:
            raise WindowCaptureError(f"window grab failed: {exc}") from exc
        frame = cv2.cvtColor(np.asarray(shot), cv2.COLOR_BGRA2BGR)
        if frame.shape[:2] != (info.height, info.width):
            raise WindowCaptureError(
                f"captured frame shape {frame.shape[:2]} != window client area "
                f"{(info.height, info.width)}"
            )
        self.last_frame_timestamp_ns = time.perf_counter_ns()
        return frame

    def get_latest_frame(self) -> np.ndarray:
        return self.get_frame()


__all__ = [
    "GameWindowError",
    "WindowCapture",
    "WindowCaptureError",
    "WindowInfo",
    "find_game_window",
    "focus_game_window",
    "validate_window_state",
    "window_info",
]