# Model default policy

Date: 2026-11-16  
Status: **old model is the default; fine-tuned model is experimental only**

## Policy

```text
default deployment / P0-C:
  runs/detect/cs2_detection_v2/weights/best.onnx        (old)

experimental / restricted branch:
  experimental/cs2_multitarget_ft_v1                     (new)
  runs/detect/cs2_multitarget_ft_v1/weights/best.onnx
```

The fine-tuned `cs2_multitarget_ft_v1` model is no longer the default. It is
retained only as an experimental/comparison branch for the 320×320 ROI domain
where it still has better in-domain metrics.

## Why

The 2026-11-16 POV audit found severe head collapse in the fine-tuned model on
1920×1080 first-person tiled inference:

| POV session | old head detections | new head detections |
|---|---:|---:|
| H | 183 | 3 |
| B | 185 | 7 |

The old model also detected 132/129 selected heads vs 2/6 for the new model.
The new model is not file-corrupt: it still has better metrics on the original
90-frame 320×320 ROI test (`head mAP50 0.922` vs `0.745`).

This is treated as a domain/scale trade-off, not a universal model improvement.

## Scope of the experimental branch

The fine-tuned model may be used only for:

- 320×320 ROI detection experiments;
- explicit A/B comparison with the old model;
- reproduction of the frozen `cs2_multitarget_ft_v1` evaluation.

It must not be used as the P0-B/P0-C POV default or advertised as a general
deployment model.

## Local-only artifacts

`run_real.py` is gitignored and local-only. Its local `_DEFAULT_WEIGHTS` now
points to the old ONNX. GitHub contains this policy and documentation, not the
private real-control entrypoint or model weights.

## References

- [`docs/research/P0B_MODEL_DEFAULT_DECISION.md`](research/P0B_MODEL_DEFAULT_DECISION.md)
- [`docs/research/P0C_MODEL_COMPARISON.md`](research/P0C_MODEL_COMPARISON.md)
- [`runs/detect/cs2_detection_v2/DEPLOYMENT_NOTE.md`](../runs/detect/cs2_detection_v2/DEPLOYMENT_NOTE.md)
- [`runs/detect/cs2_multitarget_ft_v1/MODEL_CARD.md`](../runs/detect/cs2_multitarget_ft_v1/MODEL_CARD.md)