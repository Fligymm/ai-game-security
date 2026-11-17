"""Prepare a 64-frame train/val head-review set for Label Studio."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def _read_counts(label_path: Path) -> tuple[int, int]:
    head = body = 0
    if label_path.exists():
        for line in label_path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if parts and parts[0] == "0":
                head += 1
            elif parts and parts[0] == "1":
                body += 1
    return head, body


def prepare(config_path: Path, output_dir: Path, per_session: int = 4) -> dict:
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True)
    rows = []
    for entry in config["sessions"]:
        if entry["split"] not in {"train", "val"}:
            continue
        session_id = entry["session_id"]
        source_images = _REPO / "datasets" / "pov_detection_v1" / "images" / entry["split"]
        source_labels = _REPO / "datasets" / "pov_detection_v1" / "labels" / entry["split"]
        candidates = []
        for image_path in sorted(source_images.glob(f"{session_id}_*.jpg")):
            head, body = _read_counts(source_labels / f"{image_path.stem}.txt")
            candidates.append((head, body, image_path))
        # Prefer head-containing frames, then body/empty as needed.
        candidates.sort(key=lambda item: (item[0] == 0, -item[0], item[1] == 0))
        selected = candidates[:per_session]
        if len(selected) < per_session:
            extra = [item for item in candidates if item not in selected]
            selected.extend(extra[: per_session - len(selected)])
        for head, body, image_path in selected:
            target = images_dir / image_path.name
            shutil.copy2(image_path, target)
            rows.append({
                "image": image_path.name,
                "session_id": session_id,
                "split": entry["split"],
                "map": entry["map"],
                "agent_type": entry["agent_type"],
                "prelabel_head": head,
                "prelabel_body": body,
            })
    (output_dir / "classes.txt").write_text("enemy_head\n", encoding="utf-8")
    with (output_dir / "review_head_checklist.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return {"images": len(rows), "sessions": len({row['session_id'] for row in rows})}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare POV head review set")
    parser.add_argument("--config", type=Path, default=Path("configs/pov_detection_sessions.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/pov_detection_v1/review_trainval_head"))
    parser.add_argument("--per-session", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.config, args.output_dir, args.per_session)
    except Exception as exc:
        print(f"[ERROR] head review preparation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())