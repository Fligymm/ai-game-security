# Replay review: old vs new ONNX

Date: 2026-11-14  
Status: **reviewed; accepted; no additional data collection**  
Data: 3 existing pilot scenes, 320×320 ROI videos, no new capture.  
Sample: 8,863 frames at 5 fps; conf=0.35, IoU=0.5, imgsz=640.

## Headline

| Metric | Old | New | Change |
|---|---:|---:|---:|
| frames sampled | 8,863 | 8,863 | — |
| boxes | 20,588 | 25,722 | +5,134 (+24.9%) |
| heads | 10,354 | 11,753 | +1,399 (+13.5%) |
| bodies | 10,234 | 13,969 | +3,735 (+36.5%) |
| empty frames | 1,033 | 412 | -621 (-60.1%) |
| multi-head frames | 2,363 | 2,852 | +489 (+20.7%) |
| head jumps | 723 | 966 | +243 (+33.6%) |
| inference p50 | 7.20 ms | 7.16 ms | -0.04 ms |
| inference p95 | 10.73 ms | 10.90 ms | +0.16 ms |

Divergence:

```text
matched boxes      19,239
old-only            1,349  (heads 1,056)
new-only            6,483  (heads 2,455)
processed FPS         62.9  (both models, includes decode)
```

## What this means

The new model is clearly more sensitive:

- it finds more heads and much more bodies;
- it leaves fewer empty frames;
- it matches 93.4% of old boxes, so it is not a completely different detector;
- 74.8% of new boxes match an old box; the remaining 25.2% are new-only;
- latency is unchanged.

The cost is visible:

- 6,483 new-only boxes, especially 4,028 new-only bodies;
- body precision on the labeled 90-frame test dropped from 0.956 to 0.875;
- head jumps rose 33.6%, although the new model also finds 13.5% more heads.

The replay is **unlabeled**. A new-only box is not automatically a false
positive: the old model was missing many multi-target boxes. The contact sheets
are the review surface.

## Per scene

| Scene | Frames | Old boxes | New boxes | Old-only | New-only | Old jumps | New jumps |
|---|---:|---:|---:|---:|---:|---:|---:|
| static_target | 2,977 | 6,532 | 9,380 | 718 | 3,566 | 257 | 303 |
| slow_strafe | 3,000 | 6,879 | 8,251 | 448 | 1,820 | 191 | 250 |
| fast_strafe | 2,886 | 7,177 | 8,091 | 183 | 1,097 | 275 | 413 |

`fast_strafe` has the largest jump increase: 275 → 413. That is the first place
to inspect, because fast movement is where target switching matters most.

## Review checklist

Review status: **completed by project owner, 2026-11-14.**  
The checklist below is retained as the review method.

Open:

- `contact_sheets/divergence_static_target_01.jpg`
- `contact_sheets/divergence_slow_strafe_01.jpg`
- `contact_sheets/divergence_fast_strafe_01.jpg`
- `divergence_frames.csv` (ranked review list)

For each new-only box, classify:

```text
real target missed by old model
edge/cropped body
background false positive
duplicate/overlap
```

Do not classify from the numeric divergence alone. Use the contact sheets and
the labeled 90-frame report as two separate evidence sources.

## Decision

The project owner reviewed the contact sheets and accepted the new model as
final for this iteration. No additional data collection is planned.

The extra body detections and the `fast_strafe` jump increase are accepted as
the known recall/precision trade-off; they are not claimed to be false-positive
free. Do not retrain from this replay alone.

Evidence:

```text
runs/eval/replay_v1_vs_v0/replay_comparison.json
runs/eval/replay_v1_vs_v0/REPLAY_COMPARISON.md
runs/eval/pilot_v1_ft_onnx/eval_report.json
```