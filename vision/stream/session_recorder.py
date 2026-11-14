"""Multimodal session recorder for the existing realtime capture path.

The recorder extends ``RealtimeAimLoop`` instead of replacing it: every frame
that already flows through ``ScreenGrabber -> AimPipeline`` can optionally be
written to a session directory together with detection/selection/control events
and a manifest.  It is intentionally independent from the anti-cheat classifier
and works in dry-run mode as well as in the real CS2 hook path.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np


SCHEMA_VERSION = "multimodal.session.v0"
MANIFEST_VERSION = "multimodal.manifest.v0"


@dataclass(frozen=True, slots=True)
class CaptureMetadata:
    """Immutable session-level metadata written next to the frames/events."""

    session_id: str
    source: str = "realtime_cs2_agent"
    game: str = "cs2_offline"
    scene: str = "unspecified"
    operator_id: str = "anonymous"
    width: int = 0
    height: int = 0
    target_fps: int = 0
    roi: tuple[int, int, int, int] | None = None
    backend: str = "unknown"
    notes: str = ""
    git_commit: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)


class SessionRecorder:
    """Write synchronized frames, events, and a manifest for one capture session.

    Parameters
    ----------
    root:
        Parent directory; the recorder creates ``root / metadata.session_id``.
    metadata:
        Session-level metadata.  ``width`` and ``height`` must be positive.
    video_fps:
        Playback/recording rate.  Clamped to ``metadata.target_fps`` so playback
        never runs faster than the source.  Frames are sampled only when this is
        lower than the source rate; original ``frame_id`` and monotonic timestamp
        are preserved in ``events.jsonl``.
    mode:
        ``"video"`` (default, one MP4) or ``"frames"`` (JPEG sequence).
    jpeg_quality:
        Quality for ``mode="frames"``.
    hash_files:
        Compute SHA-256 for manifest entries at ``close()``.
    """

    def __init__(
        self,
        root: str | Path,
        metadata: CaptureMetadata,
        *,
        video_fps: int = 60,
        mode: str = "video",
        jpeg_quality: int = 92,
        hash_files: bool = True,
    ) -> None:
        if metadata.width <= 0 or metadata.height <= 0:
            raise ValueError("CaptureMetadata.width and height must be positive")
        if video_fps <= 0:
            raise ValueError("video_fps must be positive")
        if mode not in {"video", "frames"}:
            raise ValueError("mode must be 'video' or 'frames'")
        if not metadata.session_id or Path(metadata.session_id).name != metadata.session_id:
            raise ValueError("session_id must be a non-empty path-safe name")

        self.root = Path(root)
        self.metadata = metadata
        # Never claim a playback rate faster than the source capture rate;
        # otherwise a 30 FPS source recorded at 60 would play at 2x speed.
        self.video_fps = int(video_fps)
        if metadata.target_fps > 0:
            self.video_fps = min(self.video_fps, int(metadata.target_fps))
        self.mode = mode
        self.jpeg_quality = int(jpeg_quality)
        self.hash_files = bool(hash_files)

        self.session_dir = self.root / metadata.session_id
        self.events_path = self.session_dir / "events.jsonl"
        self.session_path = self.session_dir / "session.json"
        self.manifest_path = self.session_dir / "manifest.json"
        self.video_path = self.session_dir / "capture.mp4"

        self._started = False
        self._closed = False
        self._events_handle: Any = None
        self._video: Any = None
        self._frames_dir: Path | None = None
        self._started_at_ns: int = 0
        self._started_at_wall_ns: int = 0
        self._last_record_ns: int | None = None
        self._last_input_timestamp_ns: int | None = None
        self._should_sample = bool(
            metadata.target_fps > 0 and self.video_fps < int(metadata.target_fps)
        )
        self._min_interval_ns = int(1_000_000_000 / self.video_fps)
        self._seen_frames = 0
        self._recorded_frames = 0
        self._skipped_frames = 0
        self._non_monotonic_timestamps = 0
        self._detections_total = 0
        self._selected_frames = 0
        self._applied_frames = 0
        self._frame_files: list[Path] = []

    def __enter__(self) -> "SessionRecorder":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> "SessionRecorder":
        if self._started:
            return self
        if self._closed:
            raise RuntimeError("SessionRecorder is already closed")

        self.session_dir.mkdir(parents=True, exist_ok=False)
        self._started_at_ns = time.perf_counter_ns()
        self._started_at_wall_ns = time.time_ns()
        self._events_handle = self.events_path.open("w", encoding="utf-8", buffering=1)

        if self.mode == "video":
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._video = cv2.VideoWriter(
                str(self.video_path),
                fourcc,
                float(self.video_fps),
                (self.metadata.width, self.metadata.height),
            )
            if not self._video.isOpened():
                self._events_handle.close()
                self._events_handle = None
                raise RuntimeError(
                    "OpenCV could not create capture.mp4; use record_mode='frames' "
                    "or install an MP4-capable OpenCV build"
                )
        else:
            self._frames_dir = self.session_dir / "frames"
            self._frames_dir.mkdir()

        self._write_session(status="recording")
        self._started = True
        return self

    def record_frame(
        self,
        frame: np.ndarray,
        *,
        timestamp_ns: int,
        frame_id: int,
        detections: Sequence[Mapping[str, Any]] = (),
        selected: Mapping[str, Any] | None = None,
        applied_mouse: bool = False,
        mouse_delta: tuple[float, float] | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> bool:
        """Record one frame if it falls on the configured sampling interval.

        Returns ``True`` when the frame was written.  The caller's ``frame_id``
        is preserved even when frames are skipped, so labels can be traced back
        to the original loop iteration.
        """

        if self._closed:
            raise RuntimeError("SessionRecorder is closed")
        if not self._started:
            self.start()

        if frame.shape[0] != self.metadata.height or frame.shape[1] != self.metadata.width:
            raise ValueError(
                f"frame shape {frame.shape[:2]} does not match metadata "
                f"{(self.metadata.height, self.metadata.width)}"
            )
        timestamp_ns = int(timestamp_ns)
        self._seen_frames += 1
        if self._last_input_timestamp_ns is not None and timestamp_ns < self._last_input_timestamp_ns:
            self._non_monotonic_timestamps += 1
        self._last_input_timestamp_ns = timestamp_ns

        if (
            self._should_sample
            and self._last_record_ns is not None
            and timestamp_ns - self._last_record_ns < self._min_interval_ns
        ):
            self._skipped_frames += 1
            return False

        record_index = self._recorded_frames
        if self.mode == "video":
            assert self._video is not None
            self._video.write(frame)
        else:
            assert self._frames_dir is not None
            path = self._frames_dir / f"frame_{record_index:06d}.jpg"
            ok = cv2.imwrite(
                str(path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
            )
            if not ok:
                raise RuntimeError(f"failed to write frame {path}")
            self._frame_files.append(path)

        event = {
            "schema_version": SCHEMA_VERSION,
            "session_id": self.metadata.session_id,
            "frame_id": int(frame_id),
            "record_index": record_index,
            "timestamp_ns": timestamp_ns,
            "wall_time_ns": time.time_ns(),
            "detections": [dict(item) for item in detections],
            "selected": dict(selected) if selected is not None else None,
            "applied_mouse": bool(applied_mouse),
            "mouse_delta": list(mouse_delta) if mouse_delta is not None else None,
            "extra": dict(extra or {}),
        }
        assert self._events_handle is not None
        self._events_handle.write(json.dumps(event, ensure_ascii=False) + "\n")

        self._last_record_ns = timestamp_ns
        self._recorded_frames += 1
        self._detections_total += len(detections)
        if selected is not None:
            self._selected_frames += 1
        if applied_mouse:
            self._applied_frames += 1
        return True

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if not self._started:
            return

        if self._video is not None:
            self._video.release()
            self._video = None
        if self._events_handle is not None:
            self._events_handle.flush()
            self._events_handle.close()
            self._events_handle = None

        self._write_session(status="closed")
        self._write_manifest()

    @property
    def duration_s(self) -> float:
        if not self._started:
            return 0.0
        return max(0.0, (time.perf_counter_ns() - self._started_at_ns) / 1_000_000_000)

    @property
    def recorded_frames(self) -> int:
        return self._recorded_frames

    def _write_session(self, *, status: str) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            **asdict(self.metadata),
            "roi": list(self.metadata.roi) if self.metadata.roi is not None else None,
            "record_mode": self.mode,
            "video_fps": self.video_fps,
            "jpeg_quality": self.jpeg_quality,
            "started_at_ns": self._started_at_ns,
            "started_at_wall_ns": self._started_at_wall_ns,
            "started_at_iso": datetime.fromtimestamp(
                self._started_at_wall_ns / 1_000_000_000, tz=timezone.utc
            ).isoformat(),
            "ended_at_ns": time.perf_counter_ns() if status == "closed" else None,
            "duration_s": self.duration_s if status == "closed" else None,
            "frames_seen": self._seen_frames,
            "frames_recorded": self._recorded_frames,
            "frames_skipped": self._skipped_frames,
            "events_path": "events.jsonl",
            "video_path": "capture.mp4" if self.mode == "video" else None,
            "frames_dir": "frames" if self.mode == "frames" else None,
        }
        self.session_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _write_manifest(self) -> None:
        files: list[dict[str, Any]] = []
        for path in self._manifest_paths():
            files.append(self._file_entry(path))
        payload = {
            "schema_version": MANIFEST_VERSION,
            "session_id": self.metadata.session_id,
            "session": asdict(self.metadata),
            "counts": {
                "frames_seen": self._seen_frames,
                "frames_recorded": self._recorded_frames,
                "frames_skipped": self._skipped_frames,
                "detections_total": self._detections_total,
                "selected_frames": self._selected_frames,
                "applied_frames": self._applied_frames,
            },
            "quality": {
                "duration_s": self.duration_s,
                "effective_fps": (
                    self._recorded_frames / self.duration_s
                    if self.duration_s > 0 and self._recorded_frames > 0
                    else 0.0
                ),
                "timestamp_monotonic": self._non_monotonic_timestamps == 0,
                "non_monotonic_timestamps": self._non_monotonic_timestamps,
            },
            "files": files,
        }
        self.manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _manifest_paths(self) -> list[Path]:
        paths: list[Path] = [self.session_path, self.events_path]
        if self.mode == "video":
            paths.append(self.video_path)
        else:
            paths.extend(self._frame_files)
        return [path for path in paths if path.exists()]

    def _file_entry(self, path: Path) -> dict[str, Any]:
        return {
            "path": path.relative_to(self.session_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": self._sha256(path) if self.hash_files else None,
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()