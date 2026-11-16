# P0-C：5H/5B tiled old-model 特征与 baseline

日期：2026-11-16  
状态：**descriptive pilot；5 H / 5 B；simple baseline 仍不支持可靠分类**

---

## 1. 输入

old 模型：

```text
runs/detect/cs2_detection_v2/weights/best.onnx
tile_size=720, grid=3, conf=0.35, iou=0.5
dry_run=true, real_control=false, apply_mouse=false
```

H：

```text
p0b_human_20261116_152512
p0b_human_20261116_205805
p0b_human_20261116_205945
p0b_human_20261116_213610
p0b_human_20261116_213729
```

B：

```text
p0b_game_bot_20261116_152746
p0b_game_bot_20261116_210201
p0b_game_bot_20261116_210336
p0b_game_bot_20261116_214003
p0b_game_bot_20261116_214446
```

所有 session 均为 60s、1920×1080、aim_botz/static_target、first_person，
并通过 `TIMEBASE_CONSISTENT`。

---

## 2. 5H vs 5B 汇总

| 指标 | H mean [min–max] | B mean [min–max] |
|---|---|---|
| detection frame ratio | 27.2% [21.7–36.7] | 28.3% [19.0–35.6] |
| selected frame ratio | 21.9% [17.6–30.7] | 22.6% [16.8–28.8] |
| mean detections/frame | 0.356 [0.272–0.505] | 0.391 [0.266–0.494] |
| selected head / body | 557 / 1,283 | 745 / 1,143 |
| selected head ratio | 30.3% | 39.5% |
| track switches mean | 59.4 | 66.4 |
| acquisition episodes mean | 74.0 | 79.2 |
| mean episode duration | 0.143 s | 0.136 s |
| mean offset | 85.2 px | 118.9 px |
| median offset | 49.2 px | 79.1 px |
| p95 offset | 311.1 px | 412.4 px |
| mean selected confidence | 0.646 | 0.709 |

观察：

- H/B 的检测覆盖、选中覆盖、episode 数范围高度重叠；
- B 的 head 比例、offset、confidence 均值略高，但单 session 范围重叠；
- 仍不能据此认为存在可靠的行为差异；
- 5 vs 5 依然是小样本。

---

## 3. 5H/5B 简单 baseline

方法：

```text
session-level 13 特征
Leave-One-Session-Out
Dummy / LogisticRegression / RandomForest(depth=2)
```

| 模型 | Accuracy | Balanced Accuracy | ROC-AUC |
|---|---:|---:|---:|
| Dummy majority | 0.500 | 0.500 | 0.500 |
| LogisticRegression | **0.600** | **0.600** | 0.680 |
| RandomForest | **0.600** | **0.600** | 0.720 |

输出：

```text
runs/eval/anticheat_p0c/baseline_v4/
├── features.csv
├── loo_predictions.csv
└── baseline_results.json
```

结论：

- 比 3H/3B 的 AUC 有轻微上升，但仍只有 6/10 正确；
- 不能作为可靠分类器；
- 不应继续在这 10 个 session 上调参追指标；
- 若继续，需更大样本或更有判别力的特征，而不是换更复杂模型。

---

## 4. 已记录的 body 漏扫

人工 QC 已确认：

```text
少量 body 漏扫
原因：训练样本少，body 动作变化后失去传统站立特征
样例极少
```

处理：

```text
accepted limitation
不重训模型
不阻断当前 pilot
后续扩样时再考虑补充 body 姿态样本
```

---

## 5. 当前结论

```text
old 模型默认
new 模型仅 experimental
5H/5B 可复现特征管线
简单 baseline 仍为负结果
不训练正式分类器
```

**P0-C 还没有达到可发表的行为分类结果；当前最大价值是模型回退、
可复现采集/推理/特征/QC 管线和负结果。**

---

## 6. 下一步

1. 不再在 5H/5B 上调参；
2. 若要继续，扩到更多独立 session；
3. 或增加更具判别力的行为特征；
4. 任何新模型/数据扩展都要重新做 QC；
5. 暂不训练正式分类器。