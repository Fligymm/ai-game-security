# Fine-tune run record: cs2_multitarget_ft_v1

Status: **completed; accepted final; no additional data collection**  
Use this file as the run log; do not edit the split after the first run.

## 1. Frozen inputs

```text
data.yaml          runs/pilot_20261115_multitarget/split_v1/data.yaml
split manifest     runs/pilot_20261115_multitarget/split_v1/split_manifest.json
dataset version    d58135a0d6e3702d
initial weights    runs/detect/cs2_detection_v2/weights/best.pt
test               runs/pilot_20261114_1920x1080/annotation (90 frames, external)
```

Data counts:

| Split | Frames | Multi | Empty | Head | Body |
|---|---:|---:|---:|---:|---:|
| train | 100 | 55 | 7 | 174 | 172 |
| val | 50 | 34 | 4 | 85 | 84 |

## 2. Fixed command

Dry-run first:

```powershell
cd <repo>

.\.venv\Scripts\python.exe tools\finetune_multitarget.py `
  --config configs\finetune_multitarget_v1.yaml
```

Start training only after the dry-run prints `"dry_run": true` with no errors:

```powershell
.\.venv\Scripts\python.exe tools\finetune_multitarget.py `
  --config configs\finetune_multitarget_v1.yaml `
  --execute
```

## 3. Fixed hyperparameters

| Parameter | Value |
|---|---|
| epochs | 50 |
| patience | 15 |
| imgsz | 640 |
| batch | 16 |
| device | 0 |
| workers | 2 |
| seed | 42 |
| deterministic | true |
| optimizer | AdamW |
| lr0 | 0.001 |
| lrf | 0.01 |
| warmup_epochs | 1.0 |
| weight_decay | 0.0005 |
| cos_lr | true |
| close_mosaic | 10 |
| mosaic | 0.5 |
| fliplr | 0.5 |
| translate | 0.1 |
| scale | 0.2 |
| mixup / copy_paste | 0.0 / 0.0 |
| run name | cs2_multitarget_ft_v1 |

If batch 16 runs out of memory, rerun with a **new run name** and `batch: 8`; do not overwrite the failed run.

## 4. Environment

```text
date/time:        2026-11-14 21:55–22:01 Asia/Shanghai
GPU:              NVIDIA GeForce RTX 4070 SUPER, 12282 MiB
torch:            2.5.1+cu121
ultralytics:      8.4.130
CUDA available:   true
epochs completed: 41 (early stop; best epoch 26, patience 15)
training time:    0.011 hours (~0.66 min)
```

## 5. Validation results

| Metric | Value |
|---|---:|
| best epoch | 26 |
| epochs completed | 41 |
| val mAP50 | 0.993 |
| val mAP50-95 | 0.618 |
| val head mAP50 | 0.995 |
| val head recall | 1.000 |
| val body mAP50 | 0.990 |
| val empty-frame FP | not separately logged (4 empty in val) |

Val set is `fast_strafe` only (50 frames); near-perfect val is expected because
the val scene is narrow. Use the external 90-frame test for the real comparison.

Artifacts:

```text
runs/detect/cs2_multitarget_ft_v1/
├── args.yaml
├── results.csv
├── weights/best.pt
├── weights/last.pt
└── weights/best.onnx       # deployment candidate
```

Record files:

```text
runs/pilot_20261115_multitarget/training_records/cs2_multitarget_ft_v1.config.json
runs/pilot_20261115_multitarget/training_records/cs2_multitarget_ft_v1.result.json
```

## 6. Test results (only after validation decision)

Evaluate the old baseline and the fine-tuned model on the same 90-frame test:

```powershell
# old baseline
.\.venv\Scripts\python.exe tools\evaluate_pilot.py `
  --model runs\detect\cs2_detection_v2\weights\best.pt `
  --annotation runs\pilot_20261114_1920x1080\annotation `
  --output runs\eval\pilot_v0_pt_control

# new fine-tuned model; do this only after freezing it
.\.venv\Scripts\python.exe tools\evaluate_pilot.py `
  --model runs\detect\cs2_multitarget_ft_v1\weights\best.pt `
  --annotation runs\pilot_20261114_1920x1080\annotation `
  --output runs\eval\pilot_v1_ft_pt
```

Compare old `best.onnx` and new `best.onnx` on the same 90-frame test:

| Metric | old best.onnx | new best.onnx | delta |
|---|---:|---:|---:|
| mAP50 | 0.785 | 0.919 | **+0.134** |
| mAP50-95 | 0.314 | 0.444 | **+0.130** |
| head mAP50 | 0.745 | 0.922 | **+0.177** |
| head P @0.35 | 0.860 | 0.965 | **+0.105** |
| head R @0.35 | 0.695 | 0.780 | **+0.085** |
| body mAP50 | 0.825 | 0.915 | **+0.090** |
| body P @0.35 | 0.956 | 0.875 | -0.081 |
| empty FP | 0 / 6 | 0 / 6 | 0 |
| inference | — | 2.9 ms | — |

Per-scene mAP50 (new ONNX):

| Scene | old | new | delta |
|---|---:|---:|---:|
| static_target | 0.682 | 0.843 | +0.161 |
| slow_strafe | 0.733 | 0.914 | +0.180 |
| fast_strafe | 0.966 | 0.995 | +0.029 |

New `best.pt` scores slightly higher on mAP50 (0.924) than new `best.onnx`
(0.919), but deployment P/R at `conf=0.35` is identical. Use the ONNX artifact
for deployment parity.

Directional gates:

```text
head mAP50 +0.03 absolute
or head recall@0.35 +0.05 absolute
body mAP50 drop <= 0.02
fast mAP50 drop <= 0.02
empty-frame FP does not increase
still within 30fps budget
```

## 7. Decision

```text
[x] keep old best.onnx as fallback
[x] adopt new best.onnx as deployment default
[x] live dry-run passed (2026-11-14, qualitative)
[x] replay contact sheets reviewed and accepted
[x] finalize; no additional data collection

reason:
All directional gates pass on the fixed 90-frame test. Head mAP50 +0.177,
head recall@0.35 +0.085, body mAP50 +0.090, fast mAP50 +0.029, empty FP
unchanged at 0/6. The live dry-run passed. The project owner reviewed the
8,863-frame old/new replay contact sheets and accepted the model.

next:
Close this iteration. Do not overwrite old best.onnx. For release, follow
`docs/OPEN_SOURCE_CHECKLIST.md` and use `MODEL_CARD.md` / `MODEL_MANIFEST.json`.
```

Evidence:

```text
runs/eval/pilot_v1_ft_pt/eval_report.json
runs/eval/pilot_v1_ft_onnx/eval_report.json
runs/eval/pilot_v1_compare/comparison.json
```

## 8. Boundaries

- Never train on `runs/pilot_20261114_1920x1080/annotation`.
- Do not tune `conf` or `imgsz` on the 90-frame test.
- The 90-frame test has now been used for one final comparison; do not reuse it
  to tune another model. Build a new held-out set for the next iteration.
- Do not edit `split_v1` after training starts; create `split_v2` if data changes.
- Keep the 11 empty frames; do not claim zero false positives from this batch.
- Record every run under a new `name`; never overwrite `cs2_multitarget_ft_v1`.
- Do not overwrite `runs/detect/cs2_detection_v2/weights/best.onnx`; keep it as
  the rollback baseline.