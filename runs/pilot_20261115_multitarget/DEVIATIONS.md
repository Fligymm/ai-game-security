# Data acceptance and deviations

Dataset: `pilot_20261115_multitarget`  
Decision: **accepted with deviation**, for `split_v1` / fine-tune candidate  
Machine-readable copy: [`deviations.json`](deviations.json)

## Final annotation state

```text
frames          150
images          150
labels          150
boxes           515
enemy_head      259
enemy_body      256
multi-target    89
empty           11
sessions         3
scenes           3
```

Label Studio export contained 160 tasks: 10 duplicate static_target images.
They were removed with `tools/dedupe_labelstudio_export.py`; 10 duplicate
groups had identical box counts and no conflicts.

## Accepted deviation

| Item | Target | Actual | Status |
|---|---:|---:|---|
| Empty frames | ≥20 | 11 | accepted for split_v1 |

Reason: the sampler chose 30 frames with no model detections, but 19 of those
frames contained visible targets that the model completely missed. Only 11
frames were truly empty after annotation.

Impact:

- empty-frame coverage is thinner than planned;
- this batch cannot be used to claim "zero false positives";
- the fixed 90-frame pilot test still contains 6 empty frames for evaluation.

Do not:

- relabel target-containing frames as empty to hit 20;
- drop the empty frames;
- present 11 empty frames as complete coverage.

Optional follow-up: capture a 30-second scene with no bots, label 9–15 true
empty frames, then regenerate the split.

## Test isolation

```text
test root       runs/pilot_20261114_1920x1080/annotation
test frames     90
included        false
hash overlap    0
session overlap 0
```

The test set is not copied into `split_v1/`.

## Split v1

```text
train: static_target + slow_strafe   100 frames, 55 multi, 7 empty
val:   fast_strafe                    50 frames, 34 multi, 4 empty
test:  pilot 90 frames                external, never train/val
```

Details: [`split_v1/split_manifest.json`](split_v1/split_manifest.json)  
Training YAML: [`split_v1/data.yaml`](split_v1/data.yaml)