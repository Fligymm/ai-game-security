"""Safety guards for realtime control loops.

Provides a small Windows global-hotkey kill switch so the user can pause or
terminate mouse output even when the preview window is not focused.
"""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from dataclasses import dataclass
from ctypes import wintypes


WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
VK_ESCAPE = 0x1B
VK_F12 = 0x7B


@dataclass(frozen=True, slots=True)
class HotkeyBindings:
    """Virtual-key bindings for the kill switch."""

    pause_vk: int = VK_ESCAPE
    stop_vk: int = VK_F12


class GlobalHotkeyKillSwitch:
    """Register global hotkeys that can pause or stop a realtime loop.

    ESC toggles the paused state for mouse output.
    F12 requests a hard stop.

    If either registration fails (for example F12 is already owned by an
    overlay), the listener falls back to polling ``GetAsyncKeyState``.  This
    keeps the same physical keys and avoids a silent loss of the kill switch.
    """

    def __init__(self, bindings: HotkeyBindings | None = None) -> None:
        self.bindings = bindings if bindings is not None else HotkeyBindings()
        self.paused = False
        self.stopped = False
        self.available = sys.platform == "win32"
        self.mode = "unstarted"

        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self._shutdown = threading.Event()

    @property
    def is_running(self) -> bool:
        """Whether the hotkey listener is currently alive and registered."""

        return bool(
            self.available
            and self._thread is not None
            and self._thread.is_alive()
            and not self.stopped
        )

    def start(self) -> GlobalHotkeyKillSwitch:
        """Start the listener thread if global hotkeys are available."""

        if not self.available or self._thread is not None:
            return self

        self._shutdown.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="GlobalHotkeyKillSwitch", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)
        return self

    def stop(self) -> None:
        """Stop the listener thread and unregister hotkeys."""

        self._shutdown.set()
        if self._thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._thread_id = None
        self._ready.clear()

    def request_stop(self) -> None:
        """Request termination of the loop and mouse output."""

        self.stopped = True
        self._shutdown.set()
        if self._thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    def toggle_pause(self) -> None:
        """Toggle mouse-output pause state."""

        self.paused = not self.paused

    def _run(self) -> None:
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        user32 = ctypes.windll.user32

        pause_ok = bool(
            user32.RegisterHotKey(None, 1, MOD_NOREPEAT, self.bindings.pause_vk)
        )
        if not pause_ok:
            self._poll_loop()
            return
        stop_ok = bool(
            user32.RegisterHotKey(None, 2, MOD_NOREPEAT, self.bindings.stop_vk)
        )
        if not stop_ok:
            user32.UnregisterHotKey(None, 1)
            self._poll_loop()
            return

        self.mode = "hotkey"
        self._ready.set()
        msg = wintypes.MSG()
        try:
            while not self._shutdown.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result <= 0:
                    break
                if msg.message == WM_HOTKEY:
                    if msg.wParam == 1:
                        self.toggle_pause()
                    elif msg.wParam == 2:
                        self.request_stop()
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            user32.UnregisterHotKey(None, 1)
            user32.UnregisterHotKey(None, 2)

    def _poll_loop(self) -> None:
        """Fallback when RegisterHotKey is unavailable or F12 is already owned."""

        self.mode = "polling"
        print(
            "[WARNING] global hotkey registration failed; "
            "using GetAsyncKeyState polling for ESC/F12"
        )
        self._ready.set()
        previous_pause = self._key_down(self.bindings.pause_vk)
        previous_stop = self._key_down(self.bindings.stop_vk)
        while not self._shutdown.is_set():
            pause_down = self._key_down(self.bindings.pause_vk)
            stop_down = self._key_down(self.bindings.stop_vk)
            if pause_down and not previous_pause:
                self.toggle_pause()
            if stop_down and not previous_stop:
                self.request_stop()
            previous_pause = pause_down
            previous_stop = stop_down
            time.sleep(0.01)

    @staticmethod
    def _key_down(vk: int) -> bool:
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
