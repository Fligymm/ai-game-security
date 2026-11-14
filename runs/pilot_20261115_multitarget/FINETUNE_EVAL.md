# Fine-tune evaluation: cs2_multitarget_ft_v1

Status: **accepted final; no additional data collection (2026-11-14)**  
Date: 2026-11-14  
Test: 90-frame pilot test, never used for training or tuning.

## Run

```text
initial weights  runs/detect/cs2_detection_v2/weights/best.pt
new weights      runs/detect/cs2_multitarget_ft_v1/weights/best.pt
new ONNX         runs/detect/cs2_multitarget_ft_v1/weights/best.onnx
dataset          split_v1, version d58135a0d6e3702d
train            100 frames (static + slow)
val               50 frames (fast)
epochs            41 completed; best epoch 26; early stop at patience 15
```

Validation on `fast_strafe`:

```text
mAP50      0.993
mAP50-95   0.618
head       0.995 / recall 1.000
body       0.990
```

Validation is not the decision metric: the val split covers only one scene.

## External 90-frame test

Old = `runs/detect/cs2_detection_v2/weights/best.onnx`  
New = `runs/detect/cs2_multitarget_ft_v1/weights/best.onnx`

| Metric | Old | New | Delta |
|---|---:|---:|---:|
| overall mAP50 | 0.785 | 0.919 | **+0.134** |
| overall mAP50-95 | 0.314 | 0.444 | **+0.130** |
| head mAP50 | 0.745 | 0.922 | **+0.177** |
| head P @0.35 | 0.860 | 0.965 | **+0.105** |
| head R @0.35 | 0.695 | 0.780 | **+0.085** |
| body mAP50 | 0.825 | 0.915 | **+0.090** |
| body P @0.35 | 0.956 | 0.875 | -0.081 |
| head FP | 16 | 4 | **-12** |
| head FN | 43 | 31 | **-12** |
| empty-frame FP | 0 / 6 | 0 / 6 | 0 |
| inference (ONNX) | — | 2.9 ms | — |

Per-scene mAP50:

| Scene | Old | New | Delta |
|---|---:|---:|---:|
| static_target | 0.682 | 0.843 | +0.161 |
| slow_strafe | 0.733 | 0.914 | +0.180 |
| fast_strafe | 0.966 | 0.995 | +0.029 |

Head-only recall at `conf=0.35`:

| Scene | Old | New | Delta |
|---|---:|---:|---:|
| static_target | 0.574 | 0.681 | +0.106 |
| slow_strafe | 0.596 | 0.712 | +0.115 |
| fast_strafe | 0.952 | 0.976 | +0.024 |

## Gates

```text
head mAP50 +0.03              +0.177  PASS
head recall@0.35 +0.05        +0.085  PASS
body mAP50 drop <= 0.02       +0.090  PASS
fast mAP50 drop <= 0.02       +0.029  PASS
empty-frame FP not increase    0 -> 0 PASS
30fps latency budget          2.9 ms  PASS
```

## Interpretation

The model no longer collapses to one or two detections in multi-target frames.
The largest gains are on `static_target` and `slow_strafe`, which were the
weakest scenes for head recall.

Caveats:

- 90 test frames is a small sample; the deltas are directional, not statistical
  proof of generalization.
- Body precision dropped by 0.081 while body recall and AP50 improved. This is
  a recall-oriented tradeoff, not hidden.
- Validation was only `fast_strafe`, so it cannot certify the other two scenes.
- The test has now been used once for model selection. Do not tune another model
  repeatedly on it; build a new held-out set for the next iteration.

## Decision

**Accepted as final and adopted as the default deployment weights on
2026-11-14.** The operator ran the short controlled live dry-run with the new
ONNX and reported it passed: FPS, selected-target stability, ROI behavior and
background frames were acceptable. The project owner then reviewed the replay
contact sheets and confirmed that the model is sufficient. No additional data
collection is planned. Exact FPS numbers were not captured, so the live check
is qualitative, not a benchmark.

Rollback remains intact:

```text
runs/detect/cs2_detection_v2/weights/best.onnx
```

`run_real.py` now uses the new ONNX by default; an explicit `--weights` still
overrides it. Do not overwrite the old model.

## Replay check without a new 3x10-minute pilot

The existing 3 pilot videos were replayed with old and new ONNX on 8,863
sampled frames. Results are in
[`runs/eval/replay_v1_vs_v0/REPLAY_REVIEW.md`](../eval/replay_v1_vs_v0/REPLAY_REVIEW.md).

```text
new boxes         25,722 vs 20,588   +24.9%
new heads         11,753 vs 10,354   +13.5%
new bodies        13,969 vs 10,234   +36.5%
empty frames          412 vs 1,033    -60.1%
new-only boxes      6,483
old-only boxes      1,349
head jumps            966 vs 723      +33.6%
inference p95      10.90 vs 10.73 ms  ~same
```

The added sensitivity is expected for multi-target data, but the new-only
bodies need visual review before calling the extra boxes a gain. Contact sheets:

```text
runs/eval/replay_v1_vs_v0/contact_sheets/divergence_static_target_01.jpg
runs/eval/replay_v1_vs_v0/contact_sheets/divergence_slow_strafe_01.jpg
runs/eval/replay_v1_vs_v0/contact_sheets/divergence_fast_strafe_01.jpg
```

Before real control, verify the ESC/F12 polling fallback because the live
dry-run logged a global-hotkey registration failure.

## Evidence

```text
runs/eval/pilot_v1_ft_pt/eval_report.json
runs/eval/pilot_v1_ft_onnx/eval_report.json
runs/eval/pilot_v1_compare/comparison.json
runs/eval/replay_v1_vs_v0/replay_comparison.json
runs/eval/replay_v1_vs_v0/REPLAY_REVIEW.md
runs/pilot_20261115_multitarget/TRAINING_RECORD.md
```