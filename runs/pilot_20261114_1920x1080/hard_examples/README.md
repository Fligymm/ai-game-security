# Missed-detection review

> 最终确认版：`review_final.csv`；原 `review.csv` 保留历史，建议过程见 `review.reclassified.csv`。

- model: `runs\detect\cs2_detection_v2\weights\best.onnx`
- conf: `0.35`
- IoU: `0.5`
- images: 90
- missed targets: 43
- by class: {'enemy_head': 43}
- by scene: {'static_target': 20, 'slow_strafe': 21, 'fast_strafe': 2}

## 怎么看

1. 先打开 `contact_sheets/`，每张表最多 8 个漏检裁剪。
2. 对每个 `#NNN` 在 `review.csv` 中填 `failure_type`，只能从以下值选：

```text
small
occluded
motion_blur
low_contrast
label_boundary
model_localization
clear_miss
other
```

> `clear_miss` 专门用于“目标清楚、无明显遮挡/模糊，模型就是没检测到”的情况；这是明确的模型漏检，不要写成 `other`。

3. 在 `notes` 里写一句原因；不确定就写 `other`，不要猜。
4. `nearest_pred_iou` 接近 0.3–0.5：可能是框偏移/定位问题；接近 0：模型完全没看到。
5. `area_px` 很小：先考虑小目标；`laplacian_var` 很低：可能模糊/低对比度；但这些只是参考，不是自动结论。

## 填完后

运行：

```powershell
.\.venv\Scripts\python.exe tools\summarize_hard_examples.py `
  --review "runs\pilot_20261114_1920x1080\hard_examples\review.csv" `
  --output "runs\pilot_20261114_1920x1080\hard_examples\review_summary.json"
```

CSV 用 Excel 保存成 GBK/ANSI 也可以，汇总脚本会自动尝试 UTF-8、GB18030、UTF-16。

或者直接把 `review.csv` 交回，我会汇总并给出下一步数据/训练决策。
