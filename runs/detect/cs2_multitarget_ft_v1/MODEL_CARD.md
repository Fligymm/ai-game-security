# Model card: cs2_multitarget_ft_v1

Status: **accepted / frozen for this iteration; NOT deployment default as of 2026-11-16**  
Accepted: 2026-11-14  
Owner decision: **model is sufficient; no additional data collection**  
Deployment note: POV audit found head collapse under 1920×1080 tiled inference;
`run_real.py` now defaults to `cs2_detection_v2/weights/best.onnx`.

## Model

```text
architecture   YOLOv8n, detect
classes        0 enemy_head, 1 enemy_body
input          320x320 ROI, imgsz=640
weights        weights/best.pt
deployment     weights/best.onnx
default        **not default as of 2026-11-16** (POV head-collapse audit)
rollback       runs/detect/cs2_detection_v2/weights/best.onnx (now deployment default)
```

Hashes and exact artifact paths are in
[`MODEL_MANIFEST.json`](MODEL_MANIFEST.json).

## Intended use

Research and controlled CS2 experiments:

- offline replay and perception evaluation;
- controlled, local CS2 sessions;
- studying detection failure modes and trajectory/selection behavior.

Out of scope:

- online competitive play or any bypass of anti-cheat;
- production anti-cheat claims;
- using the 90-frame test as a general accuracy estimate;
- claiming the model detects every target or never false-positives.

This is a research artifact, not a product. Real control remains explicit via
`run_real.py`; the default rehearsal path is still dry-run.

## Training data

```text
dataset version   d58135a0d6e3702d
source            150 frames, 3 sessions / 3 scenes
boxes             515 (head 259 / body 256)
multi-target      89 frames with 2+ heads
empty             11 frames (accepted deviation from >=20)
geometry          320x320 ROI JPG
split             train 100 (static + slow), val 50 (fast)
test              90 frames, external, never trained
```

Details:

- [`DATASET_CARD.md`](../../pilot_20261115_multitarget/DATASET_CARD.md)
- [`DEVIATIONS.md`](../../pilot_20261115_multitarget/DEVIATIONS.md)
- [`split_manifest.json`](../../pilot_20261115_multitarget/split_v1/split_manifest.json)

## Training

```text
initial weights   cs2_detection_v2/best.pt
config            configs/finetune_multitarget_v1.yaml
epochs            50 max; best epoch 26; stopped at 41
seed              42
batch             16
lr0               0.001 AdamW
imgsz             640
```

Run record:
[`TRAINING_RECORD.md`](../../pilot_20261115_multitarget/TRAINING_RECORD.md).

## Evaluation

External 90-frame test, old vs new ONNX:

| Metric | Old | New |
|---|---:|---:|
| mAP50 | 0.785 | **0.919** |
| mAP50-95 | 0.314 | **0.444** |
| head mAP50 | 0.745 | **0.922** |
| head R @0.35 | 0.695 | **0.780** |
| body mAP50 | 0.825 | **0.915** |
| empty false positives | 0 / 6 | **0 / 6** |

Full report:
[`FINETUNE_EVAL.md`](../../pilot_20261115_multitarget/FINETUNE_EVAL.md).

## Replay check

Existing pilot videos were replayed without new capture:

```text
8,863 sampled frames
boxes         20,588 -> 25,722
heads         10,354 -> 11,753
bodies        10,234 -> 13,969
empty frames   1,033 -> 412
new-only       6,483 boxes (4,028 body)
head jumps       723 -> 966 (top-confidence proxy)
```

The project owner reviewed the divergence sheets and accepted the model without
adding data:

[`REPLAY_REVIEW.md`](../../eval/replay_v1_vs_v0/REPLAY_REVIEW.md).

## Limitations

- 90 test frames is a small sample; metrics are directional.
- The test has already been used for this iteration; do not tune another model
  repeatedly on it.
- `static_target` head recall at 0.35 remains the weakest scene (~0.681).
- New body recall improved, but body precision dropped; extra body boxes are an
  accepted recall/precision trade-off, not proven zero-false-positive behavior.
- Validation was `fast_strafe` only.
- The live check was qualitative; exact end-to-end FPS/selection statistics were
  not captured.
- The live dry-run logged global-hotkey registration fallback; verify ESC/F12
  before real control.
- Empty-frame evidence is 6 labeled test frames and 11 accepted empty training
  frames, not a general background guarantee.

## Deployment

**2026-11-16 update:** `run_real.py` now defaults to the pre-finetune
`runs/detect/cs2_detection_v2/weights/best.onnx` after a POV audit found severe
head collapse in this fine-tuned model under 1920×1080 tiled inference. This
model remains a candidate/rollback and is not the deployment default.

Explicit override to this fine-tuned model:

```powershell
python run_real.py `
  --weights "runs\detect\cs2_multitarget_ft_v1\weights\best.onnx"
```

Keep the pre-finetune model as the current default/rollback. Do not overwrite
either artifact.

**Use real control only through the explicit entrypoint.** The 2026-11-14
review found and fixed a `log_only` path that could forward movement to the real
backend while paused/stopped. The fix has stopped/paused regression tests, and
the project owner reports physical ESC/F12 validation passed. The default
rehearsal path is still dry-run; keep the kill switch available and use
`run_real.py` only in the controlled local environment.

## Release / open-source notes

Before publishing:

- project code/documentation is MIT (`Copyright (c) 2026 Fligymm`); model
  weights and dataset rights are **not** covered by that license and remain
  separate decisions;
- scrub account UI, player names, chat, and raw CS2 screenshots;
- decide whether to publish weights and labels; raw footage should be reviewed;
- keep the safety constraints and dry-run default intact;
- do not advertise this as a general anti-cheat or aimbot-detection product;
- read the academic-use/prohibition notice before any use.

See [`LICENSE`](../../../LICENSE), [`RIGHTS.md`](../../../RIGHTS.md),
[`ACADEMIC_USE_NOTICE.md`](../../../docs/ACADEMIC_USE_NOTICE.md),
[`LEGAL_AND_ETHICS.md`](../../../docs/LEGAL_AND_ETHICS.md), and
[`OPEN_SOURCE_CHECKLIST.md`](../../../docs/OPEN_SOURCE_CHECKLIST.md).