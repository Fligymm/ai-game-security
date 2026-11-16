# Deployment note: pre-finetune detector

As of **2026-11-16**, this model is the default for `run_real.py` and
`tools/run_cv_agent_offline.py`.

Reason: the fine-tuned ROI model `cs2_multitarget_ft_v1` showed severe head
collapse on 1920×1080 first-person tiled inference:

| POV session | old head detections | new head detections |
|---|---:|---:|
| H | 183 | 3 |
| B | 185 | 7 |

The fine-tuned model remains a candidate/comparison artifact. It still has
better in-domain 320×320 ROI metrics, so this is a domain/scale trade-off, not a
claim that its weights are corrupt.

Training facts from `args.yaml` / `results.csv`:

```text
architecture   YOLOv8n
initial model  yolov8n.pt
input          full-screen 2560x1440 images, imgsz=640
train          119 images / 270 boxes (head 135 / body 135)
val             30 images /  66 boxes (head  33 / body  33)
epochs          50
best val mAP50  ~0.61 (from results.csv)
```

Do not overwrite this artifact. See
[`docs/research/P0B_MODEL_DEFAULT_DECISION.md`](../../../docs/research/P0B_MODEL_DEFAULT_DECISION.md)
for the full analysis.