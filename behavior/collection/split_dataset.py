"""Match cs2_custom labels to raw_images, then split 80/20 into train/val.

Does not change vision detectors, stream processors, or data.yaml class ids
(0=enemy_head, 1=enemy_body). Destination label files are renamed to the
matched image stem so Ultralytics can pair them.
"""

from __future__ import annotations

import argparse
import random
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_DEST = _REPO_ROOT / "datasets" / "cs2_custom"
DEFAULT_IMAGES = DEFAULT_DEST / "raw_images"
DEFAULT_LABELS = DEFAULT_DEST / "labels"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
_SKIP_LABEL_NAMES = {"classes.txt", "notes.txt", "labels.txt"}
_HASH_PREFIX = re.compile(r"^[0-9a-fA-F]{6,32}__")


def core_filename_stem(label_path: Path) -> str:
    """Strip Label Studio hash / URL-encoded path prefixes; keep the image stem."""
    stem = unquote(label_path.stem)
    stem = stem.replace("%5C", "\\").replace("%5c", "\\")
    stem = unquote(stem)
    if _HASH_PREFIX.match(stem):
        stem = stem.split("__", 1)[1]
        stem = unquote(stem.replace("%5C", "\\"))
    elif "__" in stem:
        stem = stem.split("__", 1)[1]
        stem = unquote(stem.replace("%5C", "\\"))
    stem = stem.replace("\\", "/").split("/")[-1]
    lower = stem.lower()
    for ext in IMAGE_EXTS:
        if lower.endswith(ext):
            stem = stem[: -len(ext)]
            break
    return stem


def index_images(images_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in sorted(images_dir.iterdir()):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        key = path.stem.lower()
        if key in index:
            print(f"[warn] duplicate image stem '{path.stem}', keeping {index[key].name}")
            continue
        index[key] = path
    return index


def collect_pairs(
    images_dir: Path, labels_dir: Path
) -> tuple[list[tuple[Path, Path]], list[Path], list[Path]]:
    """Match label txt files to raw images via exact then core-stem lookup."""
    image_index = index_images(images_dir)
    paired: list[tuple[Path, Path]] = []
    orphans: list[Path] = []
    used_images: set[Path] = set()

    labels = sorted(
        p
        for p in labels_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".txt"
        and p.name.lower() not in _SKIP_LABEL_NAMES
        and p.name != ".gitkeep"
    )

    for label in labels:
        exact = image_index.get(label.stem.lower())
        core = core_filename_stem(label)
        fuzzy = image_index.get(core.lower())
        image = exact or fuzzy
        if image is None:
            orphans.append(label)
            print(f"[warn] orphan label (no matching image): {label.name} -> core='{core}'")
            continue
        if image in used_images:
            orphans.append(label)
            print(
                f"[warn] label maps to already-paired image {image.name}, skipped: {label.name}"
            )
            continue
        paired.append((image, label))
        used_images.add(image)

    unlabeled = sorted(
        path for path in image_index.values() if path not in used_images
    )
    for image in unlabeled:
        print(f"[warn] unlabeled image (no matching .txt), skipped: {image.name}")
    return paired, unlabeled, orphans


def split_pairs(
    paired: list[tuple[Path, Path]],
    train_ratio: float,
    seed: int,
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Path]]]:
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be in (0, 1)")
    if not paired:
        return [], []

    shuffled = list(paired)
    random.Random(seed).shuffle(shuffled)
    n_train = int(round(len(shuffled) * train_ratio))
    n_train = min(max(n_train, 1), len(shuffled) - 1) if len(shuffled) > 1 else 1
    return shuffled[:n_train], shuffled[n_train:]


def _clear_split_dir(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for path in folder.iterdir():
        if path.is_file() and path.name != ".gitkeep":
            path.unlink()


def distribute(
    pairs: list[tuple[Path, Path]],
    images_out: Path,
    labels_out: Path,
) -> None:
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)
    for image, label in pairs:
        shutil.copy(str(image), str(images_out / image.name))
        dest_label = labels_out / f"{image.stem}.txt"
        shutil.copy(str(label), str(dest_label))


def run_split(
    images_dir: Path = DEFAULT_IMAGES,
    labels_dir: Path = DEFAULT_LABELS,
    dest: Path = DEFAULT_DEST,
    train_ratio: float = 0.8,
    seed: int = 42,
) -> dict[str, int]:
    images_dir = images_dir.resolve()
    labels_dir = labels_dir.resolve()
    dest = dest.resolve()
    if not images_dir.is_dir():
        raise FileNotFoundError(f"raw images directory not found: {images_dir}")
    if not labels_dir.is_dir():
        raise FileNotFoundError(f"labels directory not found: {labels_dir}")

    print(f"images_dir : {images_dir}")
    print(f"labels_dir : {labels_dir}")
    print(f"dest       : {dest}")
    print(f"split      : train={train_ratio:.0%}  val={1.0 - train_ratio:.0%}  seed={seed}")

    paired, unlabeled, orphans = collect_pairs(images_dir, labels_dir)
    train_pairs, val_pairs = split_pairs(paired, train_ratio, seed)

    for split_name in ("train", "val"):
        _clear_split_dir(dest / split_name / "images")
        _clear_split_dir(dest / split_name / "labels")

    distribute(train_pairs, dest / "train" / "images", dest / "train" / "labels")
    distribute(val_pairs, dest / "val" / "images", dest / "val" / "labels")

    summary = {
        "paired": len(paired),
        "train": len(train_pairs),
        "val": len(val_pairs),
        "unlabeled": len(unlabeled),
        "orphan_labels": len(orphans),
    }
    print("----------")
    print(f"matched pairs          : {summary['paired']}")
    print(f"unmatched images       : {summary['unlabeled']}")
    print(f"unmatched/orphan labels: {summary['orphan_labels']}")
    print(f"train copies           : {summary['train']}")
    print(f"val copies             : {summary['val']}")
    return summary


def _self_test() -> None:
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="cs2_split_"))
    images_dir = tmp / "raw_images"
    labels_dir = tmp / "labels"
    dest = tmp / "cs2_custom"
    images_dir.mkdir()
    labels_dir.mkdir()

    for i in range(10):
        (images_dir / f"ct{i:02d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        if i < 8:
            encoded = (
                f"{i:08x}__AI_Security%5Cai-game-security%5Cdatasets"
                f"%5Ccs2_custom%5Craw_images%5Cct{i:02d}.txt"
            )
            (labels_dir / encoded).write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    (labels_dir / "deadbeef__AI_Security%5Craw_images%5Cmissing.txt").write_text(
        "1 0.2 0.2 0.1 0.1\n", encoding="utf-8"
    )

    summary = run_split(
        images_dir=images_dir,
        labels_dir=labels_dir,
        dest=dest,
        train_ratio=0.8,
        seed=42,
    )
    assert summary["paired"] == 8
    assert summary["train"] == 6 and summary["val"] == 2
    assert summary["unlabeled"] == 2
    assert summary["orphan_labels"] == 1
    for folder in (dest / "train", dest / "val"):
        stems_img = {p.stem for p in (folder / "images").glob("*.png")}
        stems_txt = {p.stem for p in (folder / "labels").glob("*.txt")}
        assert stems_img == stems_txt
        for name in stems_img:
            assert not name.startswith("deadbeef")
            assert "__" not in name
    shutil.rmtree(tmp, ignore_errors=True)
    print("self-check  : passed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match raw_images to Label Studio YOLO txt labels and split 80/20."
    )
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return
    run_split(
        images_dir=args.images_dir,
        labels_dir=args.labels_dir,
        dest=args.dest,
        train_ratio=args.train_ratio,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# PowerShell (repo root, venv activated)
#
#   python behavior\collection\split_dataset.py --self-test
#   python behavior\collection\split_dataset.py
#   python train.py
# ---------------------------------------------------------------------------
