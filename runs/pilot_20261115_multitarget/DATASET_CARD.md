# Dataset Card: CS2 Multi-Target Detection v1

Status: **split frozen; `cs2_multitarget_ft_v1` accepted final; no additional data collection.**  
Dataset version: `d58135a0d6e3702d`  
Created: 2026-11-14

## 1. Purpose

This dataset adds multi-target CS2 head/body examples to address the failure
mode found in the 90-frame pilot test: the current model often detects only
0–2 heads when 2–4 are visible.

It is intended for **fine-tuning the existing detector**, not for replacing the
90-frame evaluation set and not for tuning `conf` or `imgsz` on the test set.

## 2. Contents

| Split | Scenes | Frames | Multi-target (2+ heads) | Empty | Head | Body |
|---|---|---:|---:|---:|---:|---:|
| train | static_target, slow_strafe | 100 | 55 | 7 | 174 | 172 |
| val | fast_strafe | 50 | 34 | 4 | 85 | 84 |
| **total** | 3 scenes | **150** | **89** | **11** | **259** | **256** |

Boxes total: **515**.

Images are 320×320 ROI crops. Classes:

```text
0 = enemy_head
1 = enemy_body
```

Sessions:

```text
static_target  realtime_cs2_agent_20261114_194803
slow_strafe    realtime_cs2_agent_20261114_200201
fast_strafe    realtime_cs2_agent_20261114_201336
```

## 3. Provenance

- Captured with the existing `vision.stream.realtime_loop` dry-run path:
  no real mouse input, safe kill switch retained.
- Desktop 2560×1440; CS2 centered 1920×1080 window; ROI 320.
- Sampled with `tools/sample_multitarget_annotation.py` (seed 42).
- Annotated in Label Studio 1.23 with `enemy_head` / `enemy_body`.
- Raw export: `annotation_multitarget/labelstudio_export.json`.
- Duplicate tasks: 10 static_target tasks from repeated import; removed with
  `tools/dedupe_labelstudio_export.py`, recorded in
  `annotation_multitarget/dedupe_report.json`.
- Converted with `tools/labelstudio_to_yolo.py`; conversion `ok=true`,
  `missing=[]`.

## 4. Split

```text
split_v1/
├── train/images/     100
├── train/labels/     100
├── val/images/        50
├── val/labels/        50
├── data.yaml
└── split_manifest.json
```

Split rule: **session-level**, never random frames.

```text
train = static_target + slow_strafe
val   = fast_strafe
test  = runs/pilot_20261114_1920x1080/annotation (90 frames, external)
```

Checks:

- no session overlap between train and val;
- no image hash overlap with the 90-frame pilot test;
- test images were not copied into `split_v1/`;
- manifest records source path, session, frame, image hash, label hash.

The 3-session split means the val set only covers `fast_strafe`; report this
limitation. With six sessions, use 4 train / 2 val instead.

## 5. Known limitations

1. **Empty coverage is below target:** 11 vs ≥20. The sampler's 30
   "model-empty" candidates produced only 11 truly empty frames; the other 19
   contained visible targets that the model missed.
2. The empty-frame gap is documented in [`DEVIATIONS.md`](DEVIATIONS.md) and
   [`deviations.json`](deviations.json). Do not claim zero false positives.
3. Only one session per scene; val scene coverage is narrow.
4. The model's own detections were used only to stratify sampling, not as ground
   truth. All labels are human annotations.
5. Raw CS2 frames are game captures; redistribution/licensing needs review.

## 6. Intended use

Recommended: fine-tune from the current
`runs/detect/cs2_detection_v2/weights/best.pt` on `split_v1` with a low learning
rate, early stopping on `fast_strafe`, and no test-time tuning.

Fixed entry point:

- config: `configs/finetune_multitarget_v1.yaml`
- runner: `tools/finetune_multitarget.py` (dry-run by default)
- run record: `runs/pilot_20261115_multitarget/TRAINING_RECORD.md`

Old data policy:

| Data | Frames | Geometry | Use |
|---|---:|---|---|
| `datasets/cs2_custom/train` | 119 | 2560×1440 full-screen | already represented in current weights |
| `datasets/cs2_custom/val` | 30 | 2560×1440 full-screen | historical control; not new ROI val |
| `split_v1` | 150 | 320×320 ROI | fine-tune train/val |
| pilot test | 90 | 320×320 ROI | final evaluation only |

Do **not** concatenate 2560×1440 full-screen images with 320×320 ROI images in
one training directory. If retraining from scratch, use old data as stage 1 and
ROI data as stage 2, or crop old images to ROI with label transforms first.

## 7. Evaluation protocol

Compare the old baseline and the fine-tuned model on the same 90-frame pilot
test; the v1 result is in [`FINETUNE_EVAL.md`](FINETUNE_EVAL.md):

```text
mAP:        conf=0.001, IoU=0.7
deployment: conf=0.35, IoU=0.5
report:     head/body P/R/mAP50/mAP50-95, per-scene, empty-frame FP, latency
```

Directional acceptance target:

```text
head mAP50 +0.03 absolute
or head recall@0.35 +0.05 absolute
body mAP50 drop <= 0.02
fast mAP50 drop <= 0.02
empty-frame false positives do not increase
still within the 30fps latency budget
```

The test set is small; treat these as directional gates, not statistical proof.

## 8. Reproduce

```powershell
.\.venv\Scripts\python.exe tools\check_multitarget_annotation.py `
  --annotation "runs\pilot_20261115_multitarget\annotation_multitarget" `
  --output "runs\pilot_20261115_multitarget\annotation_multitarget\check.json"

.\.venv\Scripts\python.exe tools\split_multitarget_dataset.py `
  --annotation "runs\pilot_20261115_multitarget\annotation_multitarget" `
  --output "runs\pilot_20261115_multitarget\split_v1" `
  --test-annotation "runs\pilot_20261114_1920x1080\annotation" `
  --train-scenes static_target slow_strafe `
  --val-scenes fast_strafe
```

## 9. Open-source notes

Safe to publish: scripts, labels, manifests, split metadata, aggregate counts,
and evaluation reports. Review before publishing raw game screenshots, model
weights, or anything containing account names/UI identifiers.