"""Ultralytics YOLOv8 detector for single OpenCV frames."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Sequence

import numpy as np

try:
    from ultralytics import YOLO
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "ultralytics is required. Install with: pip install ultralytics"
    ) from exc

from vision.detection.detection import Detection

CoordSpace = Literal["pixel", "normalized"]


class YOLODetector:
    """Generic YOLOv8 wrapper around Ultralytics.

    Parameters
    ----------
    weights:
        Local checkpoint or pretrained name, e.g. ``yolov8n.pt``.
    conf:
        Confidence threshold passed to ``predict``.
    iou:
        NMS IoU threshold.
    device:
        Ultralytics device string (``cpu``, ``cuda``, ``0``, …). ``None``
        lets Ultralytics pick CUDA when available.
    imgsz:
        Inference image size.
    coord_space:
        ``pixel`` returns xyxy in image pixels; ``normalized`` returns
        xyxy in ``[0, 1]`` relative to frame width/height.
    classes:
        Optional class-id filter forwarded to Ultralytics.
    """

    def __init__(
        self,
        weights: str | Path = "yolov8n.pt",
        *,
        conf: float = 0.25,
        iou: float = 0.45,
        device: str | int | None = None,
        imgsz: int = 640,
        coord_space: CoordSpace = "pixel",
        classes: Sequence[int] | None = None,
    ) -> None:
        if coord_space not in ("pixel", "normalized"):
            raise ValueError("coord_space must be 'pixel' or 'normalized'")
        if not 0.0 <= conf <= 1.0:
            raise ValueError("conf must be in [0, 1]")
        if not 0.0 <= iou <= 1.0:
            raise ValueError("iou must be in [0, 1]")

        self.weights = str(weights)
        self.conf = float(conf)
        self.iou = float(iou)
        self.device = device
        self.imgsz = int(imgsz)
        self.coord_space: CoordSpace = coord_space
        self.classes = list(classes) if classes is not None else None

        self.model = YOLO(self.weights)
        self.class_names: dict[int, str] = {
            int(k): str(v) for k, v in self.model.names.items()
        }

    def detect_frame(self, frame: np.ndarray) -> list[Detection]:
        """Run detection on one BGR OpenCV frame.

        Returns
        -------
        list of :class:`vision.detection.detection.Detection`
            Boxes are clipped to the frame (or to ``[0, 1]`` when
            ``coord_space='normalized'``). Empty list if nothing is kept.
        """
        self._validate_frame(frame)
        height, width = frame.shape[:2]

        results = self.model.predict(
            source=frame,
            conf=self.conf,
            iou=self.iou,
            device=self.device,
            imgsz=self.imgsz,
            classes=self.classes,
            verbose=False,
        )
        if not results:
            return []

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return []

        xyxy = (
            boxes.xyxyn.cpu().numpy()
            if self.coord_space == "normalized"
            else boxes.xyxy.cpu().numpy()
        )
        confs = boxes.conf.cpu().numpy()
        clss = boxes.cls.cpu().numpy()

        detections: list[Detection] = []
        for i in range(xyxy.shape[0]):
            x1, y1, x2, y2 = (float(v) for v in xyxy[i][:4])
            if self.coord_space == "normalized":
                x1 = _clip(x1, 0.0, 1.0)
                y1 = _clip(y1, 0.0, 1.0)
                x2 = _clip(x2, 0.0, 1.0)
                y2 = _clip(y2, 0.0, 1.0)
            else:
                x1 = _clip(x1, 0.0, float(width))
                y1 = _clip(y1, 0.0, float(height))
                x2 = _clip(x2, 0.0, float(width))
                y2 = _clip(y2, 0.0, float(height))

            if x2 <= x1 or y2 <= y1:
                continue

            detections.append(Detection(x1, y1, x2, y2, float(confs[i]), int(clss[i])))
        return detections

    @staticmethod
    def _validate_frame(frame: np.ndarray) -> None:
        if not isinstance(frame, np.ndarray):
            raise TypeError("frame must be a numpy.ndarray (OpenCV BGR image)")
        if frame.ndim != 3 or frame.shape[2] not in (3, 4):
            raise ValueError("frame must have shape (H, W, 3) or (H, W, 4)")
        if frame.size == 0:
            raise ValueError("frame is empty")


def _clip(value: float, low: float, high: float) -> float:
    return float(min(max(value, low), high))


if __name__ == "__main__":
    import argparse
    import sys

    import cv2

    parser = argparse.ArgumentParser(description="Smoke-test YOLODetector")
    parser.add_argument(
        "--weights",
        default="yolov8n.pt",
        help="Custom or pretrained weights (default: yolov8n.pt)",
    )
    parser.add_argument(
        "--image",
        default=None,
        help="Optional image path. If omitted, a synthetic BGR frame is used.",
    )
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument(
        "--normalized",
        action="store_true",
        help="Return boxes in [0, 1] instead of pixels.",
    )
    args = parser.parse_args()

    if args.image:
        frame = cv2.imread(args.image)
        if frame is None:
            print(f"Failed to read image: {args.image}", file=sys.stderr)
            sys.exit(1)
        source = args.image
    else:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(frame, (80, 60), (300, 400), (40, 180, 40), -1)
        cv2.circle(frame, (450, 220), 70, (0, 0, 200), -1)
        source = "synthetic BGR frame (480x640)"

    detector = YOLODetector(
        args.weights,
        conf=args.conf,
        coord_space="normalized" if args.normalized else "pixel",
    )
    detections = detector.detect_frame(frame)

    print(f"weights     : {detector.weights}")
    print(f"source      : {source}")
    print(f"frame shape : {frame.shape}")
    print(f"coord_space : {detector.coord_space}")
    print(f"num dets    : {len(detections)}")
    print("format      : [x1, y1, x2, y2, conf, cls]")
    for det in detections:
        x1, y1, x2, y2, conf, cls_id = det.row
        name = detector.class_names.get(int(cls_id), str(cls_id))
        print(
            f"  [{x1:.4f}, {y1:.4f}, {x2:.4f}, {y2:.4f}, "
            f"{conf:.4f}, {int(cls_id)}]  {name}"
        )

    assert isinstance(detections, list)
    for det in detections:
        x1, y1, x2, y2, conf, cls_id = det.row
        assert x2 > x1 and y2 > y1
        assert 0.0 <= float(conf) <= 1.0
        if detector.coord_space == "normalized":
            assert 0.0 <= x1 <= 1.0 and 0.0 <= x2 <= 1.0
            assert 0.0 <= y1 <= 1.0 and 0.0 <= y2 <= 1.0
    print("self-check  : passed")
