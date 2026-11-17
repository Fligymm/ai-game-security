"""Merge reviewed head labels into train/val while preserving prelabel bodies."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def merge(labels_root: Path, review_labels: Path, *, execute: bool) -> dict:
    index: dict[str, tuple[Path, str]] = {}
    for split in ("train", "val"):
        path = labels_root / split
        for label in path.glob("*.txt"):
            index[label.stem] = (label, split)
    reviewed = sorted(review_labels.glob("*.txt"))
    missing = [path.stem for path in reviewed if path.stem not in index]
    report = {"reviewed": len(reviewed), "missing": missing, "updated": 0, "dry_run": not execute, "files": []}
    if missing:
        report["ok"] = False
        return report
    for source in reviewed:
        target, split = index[source.stem]
        body_lines = [
            line for line in target.read_text(encoding="utf-8").splitlines()
            if line.strip() and line.split()[0] == "1"
        ]
        head_lines = [
            line for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip() and line.split()[0] == "0"
        ]
        merged = head_lines + body_lines
        if execute:
            backup = labels_root / f"{split}_head_backup" / target.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                shutil.copy2(target, backup)
            target.write_text("\n".join(merged) + ("\n" if merged else ""), encoding="utf-8")
        report["updated"] += 1
        report["files"].append({"image": source.stem, "split": split, "head": len(head_lines), "body": len(body_lines)})
    report["ok"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge reviewed head labels")
    parser.add_argument("--labels-root", type=Path, default=Path("datasets/pov_detection_v1/labels"))
    parser.add_argument("--review-labels", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    result = merge(args.labels_root, args.review_labels, execute=args.execute)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    print(text)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())