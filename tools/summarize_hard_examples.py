"""Summarize the manual failure_type review of missed detections."""

from __future__ import annotations

import argparse
import csv
import io
import json
from collections import Counter
from pathlib import Path

ALLOWED = {
    "small",
    "occluded",
    "motion_blur",
    "low_contrast",
    "label_boundary",
    "model_localization",
    "clear_miss",
    "other",
}


def _read_review_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("review.csv", raw, 0, len(raw), "unsupported encoding")


def summarize(review_path: Path) -> dict:
    rows = list(csv.DictReader(io.StringIO(_read_review_text(review_path))))
    missing = [row["crop"] for row in rows if not (row.get("failure_type") or "").strip()]
    invalid = [
        (row["crop"], row.get("failure_type"))
        for row in rows
        if (row.get("failure_type") or "").strip()
        and row["failure_type"].strip() not in ALLOWED
    ]
    counts = Counter(row["failure_type"].strip() for row in rows if row.get("failure_type"))
    by_scene: dict[str, Counter] = {}
    by_class: dict[str, Counter] = {}
    for row in rows:
        failure = (row.get("failure_type") or "").strip()
        scene = row.get("scene", "unknown")
        class_name = row.get("class_name", "unknown")
        by_scene.setdefault(scene, Counter())[failure or "unreviewed"] += 1
        by_class.setdefault(class_name, Counter())[failure or "unreviewed"] += 1
    total = len(rows)
    reviewed = total - len(missing)
    return {
        "ok": not missing and not invalid,
        "review": str(review_path),
        "total": total,
        "reviewed": reviewed,
        "missing": missing,
        "invalid": [{"crop": crop, "failure_type": value} for crop, value in invalid],
        "counts": dict(counts),
        "by_scene": {key: dict(value) for key, value in by_scene.items()},
        "by_class": {key: dict(value) for key, value in by_class.items()},
        "allowed": sorted(ALLOWED),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize missed-detection review CSV")
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = summarize(args.review)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()