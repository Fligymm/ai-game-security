"""Frame stream processing: file / camera / screen + YOLO overlay and trajectories."""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vision.detection.detection import Detection
from vision.detection.yolo_detector import YOLODetector

SourceKind = str  # "file" | "camera" | "screen"


@dataclass(frozen=True)
class TrajectoryPoint:
    """One target-center observation used for smoothness / aim analysis."""

    frame_idx: int
    x: float
    y: float
    conf: float
    cls_id: int


class _ScreenCapture:
    """Full-desktop grabber with a VideoCapture-like ``read`` / ``release`` API."""

    def __init__(self) -> None:
        try:
            from PIL import ImageGrab
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Screen capture requires Pillow. Install with: pip install Pillow"
            ) from exc
        self._grab = ImageGrab.grab

    def isOpened(self) -> bool:  # noqa: N802 — OpenCV-compatible name
        return True

    def get(self, _prop: int) -> float:
        return 0.0

    def read(self) -> tuple[bool, np.ndarray | None]:
        image = self._grab()
        frame = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
        return True, frame

    def release(self) -> None:
        return None


class VideoProcessor:
    """Run ``YOLODetector`` on a video file, webcam, or screen stream.

    Parameters
    ----------
    source:
        Video path (``.mp4`` etc.), camera index (``0``), ``"camera"``,
        or ``"screen"`` for a desktop grab (Pillow ``ImageGrab``).
    detector:
        Existing detector. If omitted, one is created from ``weights``.
    show:
        If True, preview annotated frames with ``cv2.imshow``.
    max_match_distance:
        Maximum pixel distance when linking centers across consecutive frames.
    """

    def __init__(
        self,
        source: str | int | Path,
        detector: YOLODetector | None = None,
        *,
        weights: str | Path = "yolov8n.pt",
        conf: float = 0.25,
        show: bool = True,
        window_name: str = "YOLO Stream",
        max_match_distance: float = 120.0,
    ) -> None:
        self.source = source
        self.show = bool(show)
        self.window_name = window_name
        self.max_match_distance = float(max_match_distance)
        self.detector = detector or YOLODetector(weights, conf=conf, coord_space="pixel")

        self.tracks: dict[int, list[TrajectoryPoint]] = defaultdict(list)
        self._next_track_id = 0
        self._capture: Any = None
        self._kind: SourceKind = "file"

    @property
    def trajectory(self) -> list[tuple[float, float]]:
        """Primary target centers ``(x, y)`` in pixel coordinates, in time order."""
        points = self.primary_track()
        return [(p.x, p.y) for p in points]

    def primary_track(self) -> list[TrajectoryPoint]:
        """Longest linked track (ties broken by lower track id)."""
        if not self.tracks:
            return []
        track_id = min(
            self.tracks,
            key=lambda tid: (-len(self.tracks[tid]), tid),
        )
        return list(self.tracks[track_id])

    def process(self, max_frames: int | None = None) -> list[tuple[float, float]]:
        """Iterate the stream, detect, annotate, optionally preview.

        Returns the primary ``(x, y)`` trajectory. Press ``q`` or Esc to stop
        when a preview window is open.
        """
        self.tracks.clear()
        self._next_track_id = 0
        self._open()
        try:
            for _frame_idx, _frame, annotated in self._iter_frames(max_frames):
                if self.show:
                    cv2.imshow(self.window_name, annotated)
                    delay = self._preview_delay_ms()
                    key = cv2.waitKey(delay) & 0xFF
                    if key in (ord("q"), 27):
                        break
        finally:
            self.release()
        return self.trajectory

    def release(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        if self.show:
            try:
                cv2.destroyWindow(self.window_name)
            except cv2.error:
                cv2.destroyAllWindows()

    def _open(self) -> None:
        kind, payload = _parse_source(self.source)
        self._kind = kind
        if kind == "screen":
            self._capture = _ScreenCapture()
            return
        if kind == "camera":
            capture = cv2.VideoCapture(int(payload))
        else:
            capture = cv2.VideoCapture(str(payload))
        if not capture.isOpened():
            raise RuntimeError(f"Failed to open video source: {self.source!r}")
        self._capture = capture

    def _iter_frames(
        self, max_frames: int | None
    ) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
        frame_idx = 0
        while True:
            if max_frames is not None and frame_idx >= max_frames:
                break
            ok, frame = self._capture.read()
            if not ok or frame is None:
                break
            if frame.ndim == 3 and frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            detections = self.detector.detect_frame(frame)
            centers = _detection_centers(detections, frame.shape)
            self._update_tracks(frame_idx, centers)
            annotated = self.annotate_frame(frame, detections)
            yield frame_idx, frame, annotated
            frame_idx += 1

    def annotate_frame(
        self,
        frame: np.ndarray,
        detections: list[Detection],
    ) -> np.ndarray:
        """Draw boxes, labels, confidences, centers, and the primary polyline."""
        canvas = frame.copy()
        names = self.detector.class_names
        height, width = canvas.shape[:2]

        for det in detections:
            x1, y1, x2, y2, conf, cls_id = _to_pixel_box(det, width, height)
            pt1 = (int(round(x1)), int(round(y1)))
            pt2 = (int(round(x2)), int(round(y2)))
            cv2.rectangle(canvas, pt1, pt2, (40, 220, 40), 2)
            cx = int(round((x1 + x2) / 2.0))
            cy = int(round((y1 + y2) / 2.0))
            cv2.circle(canvas, (cx, cy), 4, (0, 0, 255), -1)
            label = f"{names.get(int(cls_id), str(int(cls_id)))} {float(conf):.2f}"
            (tw, th), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            top = max(pt1[1], th + 6)
            cv2.rectangle(
                canvas,
                (pt1[0], top - th - 6),
                (pt1[0] + tw + 4, top + baseline - 2),
                (40, 220, 40),
                -1,
            )
            cv2.putText(
                canvas,
                label,
                (pt1[0] + 2, top - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
                cv2.LINE_AA,
            )

        primary = [(int(round(p.x)), int(round(p.y))) for p in self.primary_track()]
        if len(primary) >= 2:
            cv2.polylines(canvas, [np.array(primary, dtype=np.int32)], False, (0, 165, 255), 2)
        return canvas

    def _update_tracks(
        self,
        frame_idx: int,
        centers: list[tuple[float, float, float, int]],
    ) -> None:
        """Greedy nearest-neighbor association of box centers across frames."""
        unused = set(range(len(centers)))
        last_by_track = {
            tid: pts[-1] for tid, pts in self.tracks.items() if pts
        }

        assignments: list[tuple[int, int, float]] = []
        for tid, last in last_by_track.items():
            best_i: int | None = None
            best_d = self.max_match_distance
            for i in unused:
                cx, cy, _conf, _cls = centers[i]
                dist = float(np.hypot(cx - last.x, cy - last.y))
                if dist < best_d:
                    best_d = dist
                    best_i = i
            if best_i is not None:
                assignments.append((tid, best_i, best_d))

        assignments.sort(key=lambda item: item[2])
        claimed_tracks: set[int] = set()
        for tid, i, _dist in assignments:
            if tid in claimed_tracks or i not in unused:
                continue
            cx, cy, conf, cls_id = centers[i]
            self.tracks[tid].append(
                TrajectoryPoint(frame_idx, cx, cy, conf, cls_id)
            )
            unused.discard(i)
            claimed_tracks.add(tid)

        for i in unused:
            cx, cy, conf, cls_id = centers[i]
            tid = self._next_track_id
            self._next_track_id += 1
            self.tracks[tid].append(
                TrajectoryPoint(frame_idx, cx, cy, conf, cls_id)
            )

    def _preview_delay_ms(self) -> int:
        if self._kind != "file" or self._capture is None:
            return 1
        fps = float(self._capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 1e-3:
            return 1
        return max(1, int(round(1000.0 / fps)))


def _parse_source(source: str | int | Path) -> tuple[SourceKind, str | int]:
    if isinstance(source, (int, np.integer)):
        return "camera", int(source)
    text = str(source).strip()
    lowered = text.lower()
    if lowered in {"screen", "desktop", "display"}:
        return "screen", text
    if lowered in {"camera", "webcam", "cam"}:
        return "camera", 0
    if text.isdigit():
        return "camera", int(text)
    return "file", text


def _to_pixel_box(
    det: Detection,
    width: int,
    height: int,
) -> tuple[float, float, float, float, float, int]:
    x1, y1, x2, y2, conf, cls_id = det.row
    x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
    if 0.0 <= x1 <= 1.0 and 0.0 <= y1 <= 1.0 and 0.0 <= x2 <= 1.0 and 0.0 <= y2 <= 1.0:
        if width > 1 and height > 1 and x2 <= 1.0:
            x1, x2 = x1 * width, x2 * width
            y1, y2 = y1 * height, y2 * height
    return x1, y1, x2, y2, float(conf), int(cls_id)


def _detection_centers(
    detections: list[Detection],
    shape: tuple[int, ...],
) -> list[tuple[float, float, float, int]]:
    height, width = shape[:2]
    centers: list[tuple[float, float, float, int]] = []
    for det in detections:
        x1, y1, x2, y2, conf, cls_id = _to_pixel_box(det, width, height)
        centers.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0, conf, cls_id))
    return centers


def write_synthetic_video(
    path: str | Path,
    *,
    n_frames: int = 90,
    fps: int = 30,
    size: tuple[int, int] = (640, 480),
    radius: int = 48,
) -> Path:
    """Write a looping BGR clip with a moving filled circle (no extra assets)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        float(fps),
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open VideoWriter for {path}")

    for i in range(n_frames):
        frame = np.full((height, width, 3), 24, dtype=np.uint8)
        t = 2.0 * np.pi * i / n_frames
        cx = int(round(width / 2.0 + (width / 2.0 - radius - 16) * np.sin(t)))
        cy = int(round(height / 2.0 + (height / 2.0 - radius - 16) * np.cos(t * 0.85)))
        cv2.circle(frame, (cx, cy), radius, (0, 0, 220), -1)
        writer.write(frame)
    writer.release()
    return path


if __name__ == "__main__":
    import argparse
    import tempfile

    parser = argparse.ArgumentParser(description="Run VideoProcessor on a stream")
    parser.add_argument(
        "--source",
        default=None,
        help="Video path, camera index, 'camera', or 'screen'. "
        "If omitted, a synthetic moving-circle mp4 is generated.",
    )
    parser.add_argument("--weights", default="yolov8n.pt")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Disable cv2.imshow (useful for headless smoke tests).",
    )
    args = parser.parse_args()

    source: str | int | Path
    if args.source is None:
        tmp = Path(tempfile.gettempdir()) / "ai_gs_synthetic_circle.mp4"
        source = write_synthetic_video(tmp)
        print(f"no --source given; wrote synthetic clip: {source}")
        if args.max_frames is None:
            args.max_frames = 60
    elif args.source.isdigit():
        source = int(args.source)
    else:
        source = args.source

    processor = VideoProcessor(
        source,
        weights=args.weights,
        conf=args.conf,
        show=not args.no_show,
    )
    trajectory = processor.process(max_frames=args.max_frames)

    print(f"source      : {source}")
    print(f"num tracks  : {len(processor.tracks)}")
    print(f"trajectory  : {len(trajectory)} points (primary target center x, y)")
    preview_n = min(8, len(trajectory))
    for x, y in trajectory[:preview_n]:
        print(f"  ({x:.2f}, {y:.2f})")
    if len(trajectory) > preview_n:
        print("  ...")

    assert isinstance(trajectory, list)
    for point in trajectory:
        assert len(point) == 2
    print("self-check  : passed")
