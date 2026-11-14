# Multi-target data collection

Status: **annotation complete; split_v1 frozen; `cs2_multitarget_ft_v1` accepted final; no additional data collection.**

See:

- [`DATASET_CARD.md`](DATASET_CARD.md)
- [`DEVIATIONS.md`](DEVIATIONS.md)
- [`FINETUNE_EVAL.md`](FINETUNE_EVAL.md)
- [`TRAINING_RECORD.md`](TRAINING_RECORD.md)
- [`MODEL_CARD.md`](../detect/cs2_multitarget_ft_v1/MODEL_CARD.md)
- [`MODEL_MANIFEST.json`](../detect/cs2_multitarget_ft_v1/MODEL_MANIFEST.json)
- [`docs/MULTITARGET_DATA_TASKBOOK.md`](../../docs/MULTITARGET_DATA_TASKBOOK.md)

Final data:

```text
150 frames
515 boxes: head 259 / body 256
89 frames with 2+ heads
11 empty frames (accepted deviation from >=20)
3 sessions / 3 scenes
```

Split:

```text
train: static_target + slow_strafe   100 frames
val:   fast_strafe                    50 frames
test:  pilot 90 frames                external, untouched
```

Outputs:

```text
captures/                    # new sessions
reports/                     # check_session JSON
replays/                     # replay MP4
annotation_multitarget/      # images, labels, manifest, reports
split_v1/                    # frozen train/val YAML and manifest
training_records/            # run config/result JSON
FINETUNE_EVAL.md             # old vs new test comparison
TRAINING_RECORD.md           # run log and decision
DATASET_CARD.md
DEVIATIONS.md / deviations.json
NOTES.md
```