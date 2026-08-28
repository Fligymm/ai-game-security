"""Offline / controlled-environment benchmarking for the vision-to-control stack.

Usage examples
--------------
python scripts/offline_benchmark.py image --image-path D:\\path\\to\\test.png
python scripts/offline_benchmark.py video --video-path D:\\path\\to\\test.mp4
python scripts/offline_benchmark.py bot --frames 240

The script is designed to run even when the real assets are not present yet:
it falls back to synthetic smoke-test inputs so the whole pipeline can be
validated end-to-end before real images or videos are added.
"""

from __future__ import annotations

import argparse
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
import sys

import cv2
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cv_agent.orchestrator import AimPipeline
from vision.detection.detection import Detection
from vision.detection.yolo_detector import YOLODetector
from vision.stream.video_processor import write_synthetic_video
from visualization.aim_debug_overlay import draw_aim_debug_overlay


DEFAULT_IMAGE_PATH = r"D:\AI_Security\ai-game-security\datasets\cs2_custom\test_images"
DEFAULT_VIDEO_PATH = r"D:\AI_Security\ai-game-security\TODO\replace_with_real_test_video.mp4"
DEFAULT_WEIGHTS_PATH = str(_REPO_ROOT / "yolov8n.pt")


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    """Compact results for one benchmark run."""

    frames: int
    detections: int
    selected_frames: int
    elapsed_s: float
    mean_fps: float


class SyntheticBotDetector:
    """Simple detector for the slow bot smoke test.

    It detects the synthetic red head marker drawn by this script and converts
    it into a Detection object so the same AimPipeline / TargetState / Kalman
    / trajectory path can be exercised without any external assets.
    """

    class_names = {0: "bot_head"}

    def detect_frame(self, frame: np.ndarray) -> list[Detection]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, (0, 120, 70), (10, 255, 255))
        mask2 = cv2.inRange(hsv, (170, 120, 70), (180, 255, 255))
        mask = cv2.bitwise_or(mask1, mask2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return []

        contour = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(contour))
        if area < 20.0:
            return []

        x, y, w, h = cv2.boundingRect(contour)
        conf = min(0.99, area / max(float(frame.shape[0] * frame.shape[1]), 1.0) * 80.0)
        return [Detection(float(x), float(y), float(x + w), float(y + h), conf, 0)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline benchmarking for the AI Game Security Lab")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    image_parser = subparsers.add_parser("image", help="Test a static image")
    image_parser.add_argument("--image-path", default=DEFAULT_IMAGE_PATH, help="Absolute image path or image directory")
    image_parser.add_argument("--weights", default=DEFAULT_WEIGHTS_PATH, help="Model weights path")
    image_parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
    image_parser.add_argument("--save-overlay", default=None, help="Optional output image path")
    image_parser.add_argument("--preview", action="store_true", help="Show a preview window")

    video_parser = subparsers.add_parser("video", help="Test an offline video")
    video_parser.add_argument("--video-path", default=DEFAULT_VIDEO_PATH, help="Absolute video path to add later")
    video_parser.add_argument("--weights", default=DEFAULT_WEIGHTS_PATH, help="Model weights path")
    video_parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
    video_parser.add_argument("--max-frames", type=int, default=120, help="Optional frame limit")
    video_parser.add_argument("--preview", action="store_true", help="Show a preview window")

    bot_parser = subparsers.add_parser("bot", help="Test a slow synthetic bot demo")
    bot_parser.add_argument("--frames", type=int, default=240, help="Number of synthetic frames to run")
    bot_parser.add_argument("--preview", action="store_true", help="Show a preview window")
    bot_parser.add_argument("--save-video", default=None, help="Optional output mp4 path")

    args = parser.parse_args()

    if args.mode == "image":
        summary = run_static_image_test(
            image_path=Path(args.image_path),
            weights_path=Path(args.weights),
            conf=float(args.conf),
            save_overlay=Path(args.save_overlay) if args.save_overlay else None,
            preview=bool(args.preview),
        )
    elif args.mode == "video":
        summary = run_video_test(
            video_path=Path(args.video_path),
            weights_path=Path(args.weights),
            conf=float(args.conf),
            max_frames=args.max_frames,
            preview=bool(args.preview),
        )
    else:
        summary = run_slow_bot_test(
            frames=int(args.frames),
            preview=bool(args.preview),
            save_video=Path(args.save_video) if args.save_video else None,
        )

    print(
        f"mode={args.mode} frames={summary.frames} detections={summary.detections} "
        f"selected_frames={summary.selected_frames} elapsed_s={summary.elapsed_s:.3f} "
        f"mean_fps={summary.mean_fps:.2f}"
    )


def run_static_image_test(
    *,
    image_path: Path,
    weights_path: Path,
    conf: float,
    save_overlay: Path | None,
    preview: bool,
) -> BenchmarkSummary:
    """Run the stack on one static image and optionally save / preview the overlay."""

    frame = _load_or_create_static_image(image_path)
    pipeline = AimPipeline(detector=_build_detector(weights_path, conf))

    start = time.perf_counter()
    result = pipeline.run(frame, apply_mouse=False)
    elapsed = time.perf_counter() - start

    overlay = draw_aim_debug_overlay(frame, result)
    if save_overlay is not None:
        save_overlay.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(save_overlay), overlay)
    if preview:
        _preview_single_frame("Offline Benchmark - Image", overlay)

    return BenchmarkSummary(
        frames=1,
        detections=len(result.detections),
        selected_frames=1 if result.selected is not None else 0,
        elapsed_s=elapsed,
        mean_fps=1.0 / max(elapsed, 1e-6),
    )


def run_video_test(
    *,
    video_path: Path,
    weights_path: Path,
    conf: float,
    max_frames: int | None,
    preview: bool,
) -> BenchmarkSummary:
    """Run the stack on a video file or a synthetic fallback clip."""

    resolved_video = _ensure_video_source(video_path)
    detector = _build_detector(weights_path, conf)
    pipeline = AimPipeline(detector=detector)

    capture = cv2.VideoCapture(str(resolved_video))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open video source: {resolved_video}")

    frames = 0
    detections = 0
    selected_frames = 0
    start = time.perf_counter()
    try:
        while max_frames is None or frames < max_frames:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            if frame.ndim == 3 and frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            result = pipeline.run(frame, apply_mouse=False)
            detections += len(result.detections)
            selected_frames += int(result.selected is not None)
            frames += 1

            if preview:
                overlay = draw_aim_debug_overlay(frame, result)
                _preview_single_frame("Offline Benchmark - Video", overlay)
    finally:
        capture.release()

    elapsed = time.perf_counter() - start
    return BenchmarkSummary(
        frames=frames,
        detections=detections,
        selected_frames=selected_frames,
        elapsed_s=elapsed,
        mean_fps=frames / max(elapsed, 1e-6),
    )


def run_slow_bot_test(
    *,
    frames: int,
    preview: bool,
    save_video: Path | None,
) -> BenchmarkSummary:
    """Run a slow moving synthetic bot demo to verify the closed-loop chain."""

    detector = SyntheticBotDetector()
    pipeline = AimPipeline(detector=detector)

    width, height = 640, 640
    writer = None
    if save_video is not None:
        save_video.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(save_video),
            cv2.VideoWriter_fourcc(*"mp4v"),
            30.0,
            (width, height),
        )
        if not writer.isOpened():
            raise RuntimeError(f"Failed to open output writer: {save_video}")

    detections = 0
    selected_frames = 0
    start = time.perf_counter()
    try:
        for _idx, frame in enumerate(_iter_slow_bot_frames(frames, width, height)):
            result = pipeline.run(frame, apply_mouse=False)
            detections += len(result.detections)
            selected_frames += int(result.selected is not None)

            overlay = draw_aim_debug_overlay(frame, result)
            if writer is not None:
                writer.write(overlay)
            if preview:
                _preview_single_frame("Offline Benchmark - Bot", overlay)
    finally:
        if writer is not None:
            writer.release()

    elapsed = time.perf_counter() - start
    return BenchmarkSummary(
        frames=frames,
        detections=detections,
        selected_frames=selected_frames,
        elapsed_s=elapsed,
        mean_fps=frames / max(elapsed, 1e-6),
    )


def _build_detector(weights_path: Path, conf: float) -> YOLODetector:
    resolved = weights_path if weights_path.exists() else Path(DEFAULT_WEIGHTS_PATH)
    if not resolved.exists():
        raise FileNotFoundError(
            f"Weights not found at {weights_path} and fallback weights missing at {resolved}"
        )
    return YOLODetector(resolved, conf=conf, coord_space="pixel")


def _load_or_create_static_image(image_path: Path) -> np.ndarray:
    if image_path.exists():
        if image_path.is_dir():
            for candidate in sorted(image_path.glob("*.png")) + sorted(image_path.glob("*.jpg")) + sorted(image_path.glob("*.jpeg")):
                frame = cv2.imread(str(candidate))
                if frame is not None:
                    return frame
        else:
            frame = cv2.imread(str(image_path))
            if frame is not None:
                return frame
    return _create_synthetic_static_image()


def _ensure_video_source(video_path: Path) -> Path:
    if video_path.exists():
        return video_path
    temp_dir = Path(tempfile.gettempdir()) / "ai_game_security_benchmarks"
    temp_dir.mkdir(parents=True, exist_ok=True)
    synthetic_path = temp_dir / "synthetic_offline_video.mp4"
    if not synthetic_path.exists():
        write_synthetic_video(synthetic_path, n_frames=120, fps=30, size=(640, 480))
    return synthetic_path


def _create_synthetic_static_image() -> np.ndarray:
    frame = np.full((640, 640, 3), 24, dtype=np.uint8)
    cv2.rectangle(frame, (120, 130), (220, 460), (40, 220, 40), -1)
    cv2.circle(frame, (420, 240), 70, (0, 0, 220), -1)
    cv2.line(frame, (80, 540), (560, 540), (255, 255, 255), 3)
    cv2.putText(
        frame,
        "Synthetic benchmark image",
        (110, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return frame


def _iter_slow_bot_frames(frames: int, width: int, height: int) -> Iterator[np.ndarray]:
    radius = 26
    start_x = 120.0
    end_x = float(width - 120)
    y = float(height // 2)
    for i in range(max(frames, 1)):
        t = i / max(frames - 1, 1)
        x = int(round(start_x + (end_x - start_x) * t))
        frame = np.full((height, width, 3), 18, dtype=np.uint8)
        cv2.circle(frame, (x, int(round(y))), radius, (0, 0, 255), -1)
        cv2.rectangle(frame, (x - 18, int(y) + 30), (x + 18, int(y) + 80), (0, 255, 0), -1)
        cv2.putText(
            frame,
            f"bot frame {i + 1}/{frames}",
            (16, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        yield frame


def _preview_single_frame(window_name: str, frame: np.ndarray) -> None:
    cv2.imshow(window_name, frame)
    cv2.waitKey(1)


if __name__ == "__main__":
    main()
