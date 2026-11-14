"""Extract missed detections from the labeled pilot for manual error analysis."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw
from ultralytics import YOLO

try:
    from tools.evaluate_pilot import _iou, _read_label
except ImportError:  # running as ``python tools/analyze_false_negatives.py``
    from evaluate_pilot import _iou, _read_label

CLASS_NAMES = {0: "enemy_head", 1: "enemy_body"}
FAILURE_TYPES = (
    "small",
    "occluded",
    "motion_blur",
    "low_contrast",
    "label_boundary",
    "model_localization",
    "clear_miss",
    "other",
)


def _matches(
    truth: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    iou_threshold: float,
) -> tuple[set[int], set[int], set[int]]:
    """Return matched GT indices, matched prediction indices, and false-positive predictions."""

    matched_truth: set[int] = set()
    matched_pred: set[int] = set()
    for class_id in CLASS_NAMES:
        gt = [(i, box) for i, box in enumerate(truth) if box["class_id"] == class_id]
        preds = [
            (i, box)
            for i, box in enumerate(predictions)
            if box["class_id"] == class_id
        ]
        preds.sort(key=lambda pair: pair[1]["confidence"], reverse=True)
        for pred_index, pred in preds:
            best_index, best_iou = None, 0.0
            for truth_index, box in gt:
                if truth_index in matched_truth:
                    continue
                overlap = _iou(box["xyxy"], pred["xyxy"])
                if overlap > best_iou:
                    best_index, best_iou = truth_index, overlap
            if best_index is not None and best_iou >= iou_threshold:
                matched_truth.add(best_index)
                matched_pred.add(pred_index)
    false_positive = {
        index for index in range(len(predictions)) if index not in matched_pred
    }
    return matched_truth, matched_pred, false_positive


def _crop_with_margin(
    image: np.ndarray,
    xyxy: list[float],
    *,
    margin_ratio: float = 0.25,
) -> np.ndarray:
    height, width = image.shape[:2]
    x1, y1, x2, y2 = xyxy
    box_w, box_h = x2 - x1, y2 - y1
    margin = max(4.0, max(box_w, box_h) * margin_ratio)
    left = max(0, int(x1 - margin))
    top = max(0, int(y1 - margin))
    right = min(width, int(x2 + margin))
    bottom = min(height, int(y2 + margin))
    return image[top:bottom, left:right].copy()


def _contact_sheets(records: list[dict[str, Any]], output_dir: Path, scene: str) -> list[str]:
    sheets: list[str] = []
    if not records:
        return sheets
    cell_w, cell_h = 220, 230
    cols, rows = 4, 2
    per_sheet = cols * rows
    for sheet_index in range(0, len(records), per_sheet):
        batch = records[sheet_index : sheet_index + per_sheet]
        canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), "white")
        draw = ImageDraw.Draw(canvas)
        for cell, record in enumerate(batch):
            image = Image.open(output_dir / record["crop"]).convert("RGB")
            image.thumbnail((cell_w - 12, cell_h - 52))
            x = (cell % cols) * cell_w + 6
            y = (cell // cols) * cell_h + 38
            canvas.paste(image, (x, y))
            label = (
                f"#{record['index']:03d} {record['class_name']} "
                f"f{record['frame_id']} area={record['area_px']:.0f} "
                f"nearest_iou={record['nearest_pred_iou']:.2f}"
            )
            draw.text((x, (cell // cols) * cell_h + 6), label, fill="black")
        sheet_name = f"{scene}_{sheet_index // per_sheet + 1:02d}.jpg"
        canvas.save(output_dir / "contact_sheets" / sheet_name, quality=95)
        for record in batch:
            record["contact_sheet"] = f"contact_sheets/{sheet_name}"
        sheets.append(sheet_name)
    return sheets


def analyze(
    model_path: Path,
    annotation_root: Path,
    output_dir: Path,
    *,
    conf: float = 0.35,
    iou: float = 0.5,
    imgsz: int = 640,
    device: str = "0",
    class_ids: tuple[int, ...] = (0,),
    crop_scale: int = 4,
) -> dict[str, Any]:
    manifest = json.loads((annotation_root / "manifest.json").read_text(encoding="utf-8"))
    items = manifest["items"]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "crops").mkdir(exist_ok=True)
    (output_dir / "contact_sheets").mkdir(exist_ok=True)

    model = YOLO(str(model_path))
    records: list[dict[str, Any]] = []
    class_counter: Counter[str] = Counter()
    scene_counter: Counter[str] = Counter()
    prediction_count = 0

    for item in items:
        image_path = annotation_root / item["image"]
        label_path = annotation_root / item["label"]
        image = cv2.imread(str(image_path))
        if image is None:
            raise RuntimeError(f"cannot decode {image_path}")
        truth = _read_label(label_path, image.shape[1], image.shape[0])
        result = model.predict(
            source=image,
            imgsz=imgsz,
            conf=conf,
            iou=iou,
            device=device,
            verbose=False,
            max_det=300,
        )[0]
        predictions: list[dict[str, Any]] = []
        if result.boxes is not None and len(result.boxes):
            for xyxy, confidence, class_id in zip(
                result.boxes.xyxy.cpu().numpy(),
                result.boxes.conf.cpu().numpy(),
                result.boxes.cls.cpu().numpy(),
            ):
                predictions.append(
                    {
                        "xyxy": [float(v) for v in xyxy],
                        "confidence": float(confidence),
                        "class_id": int(class_id),
                    }
                )
        prediction_count += len(predictions)
        matched_truth, _, _ = _matches(truth, predictions, iou)

        for truth_index, box in enumerate(truth):
            if truth_index in matched_truth or box["class_id"] not in class_ids:
                continue
            class_id = int(box["class_id"])
            class_name = CLASS_NAMES[class_id]
            x1, y1, x2, y2 = box["xyxy"]
            same_class = [p for p in predictions if p["class_id"] == class_id]
            nearest = max(
                same_class,
                key=lambda pred: _iou(box["xyxy"], pred["xyxy"]),
                default=None,
            )
            nearest_iou = _iou(box["xyxy"], nearest["xyxy"]) if nearest else 0.0
            crop = _crop_with_margin(image, box["xyxy"])
            if crop.size == 0:
                continue
            crop = cv2.resize(
                crop,
                None,
                fx=crop_scale,
                fy=crop_scale,
                interpolation=cv2.INTER_NEAREST,
            )
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            index = len(records)
            crop_name = (
                f"{index:03d}_{item['scene']}_f{int(item['frame_id']):06d}_"
                f"{class_name}.jpg"
            )
            crop_path = output_dir / "crops" / crop_name
            cv2.imwrite(str(crop_path), crop)
            records.append(
                {
                    "index": index,
                    "crop": f"crops/{crop_name}",
                    "contact_sheet": "",
                    "scene": item["scene"],
                    "session_id": item["session_id"],
                    "frame_id": int(item["frame_id"]),
                    "class_id": class_id,
                    "class_name": class_name,
                    "x1": round(float(x1), 2),
                    "y1": round(float(y1), 2),
                    "x2": round(float(x2), 2),
                    "y2": round(float(y2), 2),
                    "area_px": round(float((x2 - x1) * (y2 - y1)), 1),
                    "width_px": round(float(x2 - x1), 1),
                    "height_px": round(float(y2 - y1), 1),
                    "nearest_pred_iou": round(float(nearest_iou), 3),
                    "nearest_pred_conf": round(float(nearest["confidence"]), 3) if nearest else 0.0,
                    "laplacian_var": round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2),
                    "std_luma": round(float(gray.std()), 2),
                    "failure_type": "",
                    "notes": "",
                }
            )
            class_counter[class_name] += 1
            scene_counter[item["scene"]] += 1

    by_scene: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_scene[record["scene"]].append(record)
    sheets: list[str] = []
    for scene, scene_records in sorted(by_scene.items()):
        sheets.extend(_contact_sheets(scene_records, output_dir, scene))

    csv_path = output_dir / "review.csv"
    fields = [
        "index",
        "crop",
        "contact_sheet",
        "scene",
        "session_id",
        "frame_id",
        "class_id",
        "class_name",
        "x1",
        "y1",
        "x2",
        "y2",
        "area_px",
        "width_px",
        "height_px",
        "nearest_pred_iou",
        "nearest_pred_conf",
        "laplacian_var",
        "std_luma",
        "failure_type",
        "notes",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    summary = {
        "ok": True,
        "model": str(model_path),
        "conf": conf,
        "iou": iou,
        "imgsz": imgsz,
        "class_ids": list(class_ids),
        "images": len(items),
        "predictions": prediction_count,
        "missed": len(records),
        "by_class": dict(class_counter),
        "by_scene": dict(scene_counter),
        "failure_types": list(FAILURE_TYPES),
        "contact_sheets": sheets,
        "review_csv": str(csv_path),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(_readme(summary), encoding="utf-8")
    return summary


def _readme(summary: dict[str, Any]) -> str:
    return f"""# Missed-detection review

- model: `{summary['model']}`
- conf: `{summary['conf']}`
- IoU: `{summary['iou']}`
- images: {summary['images']}
- missed targets: {summary['missed']}
- by class: {summary['by_class']}
- by scene: {summary['by_scene']}

## 怎么看

1. 先打开 `contact_sheets/`，每张表最多 8 个漏检裁剪。
2. 对每个 `#NNN` 在 `review.csv` 中填 `failure_type`，只能从以下值选：

```text
{chr(10).join(summary['failure_types'])}
```

3. 在 `notes` 里写一句原因；不确定就写 `other`，不要猜。
4. `nearest_pred_iou` 接近 0.3–0.5：可能是框偏移/定位问题；接近 0：模型完全没看到。
5. `area_px` 很小：先考虑小目标；`laplacian_var` 很低：可能模糊/低对比度；但这些只是参考，不是自动结论。

## 填完后

运行：

```powershell
python tools/summarize_hard_examples.py `
  --review "runs/pilot_20261114_1920x1080/hard_examples/review.csv"
```

或者直接把 `review.csv` 交回，我会汇总并给出下一步数据/训练决策。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract missed detections for review")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default="0")
    parser.add_argument("--class-id", action="append", type=int, default=None)
    parser.add_argument("--crop-scale", type=int, default=4)
    args = parser.parse_args()

    summary = analyze(
        args.model,
        args.annotation,
        args.output,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        device=args.device,
        class_ids=tuple(args.class_id) if args.class_id else (0,),
        crop_scale=args.crop_scale,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()