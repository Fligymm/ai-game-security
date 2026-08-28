"""Video and camera/screen streams with per-frame detection."""

from .grabber import ScreenGrabber
from .realtime_loop import RealtimeAimLoop, RealtimeLoopConfig
from .safety import GlobalHotkeyKillSwitch
from .video_processor import VideoProcessor

__all__ = [
	"GlobalHotkeyKillSwitch",
	"RealtimeAimLoop",
	"RealtimeLoopConfig",
	"ScreenGrabber",
	"VideoProcessor",
]
