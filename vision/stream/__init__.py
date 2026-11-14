"""Video and camera/screen streams with per-frame detection."""

from .grabber import ScreenGrabber
from .realtime_loop import RealtimeAimLoop, RealtimeLoopConfig
from .safety import GlobalHotkeyKillSwitch
from .session_recorder import CaptureMetadata, SessionRecorder
from .video_processor import VideoProcessor

__all__ = [
	"CaptureMetadata",
	"GlobalHotkeyKillSwitch",
	"RealtimeAimLoop",
	"RealtimeLoopConfig",
	"ScreenGrabber",
	"SessionRecorder",
	"VideoProcessor",
]
