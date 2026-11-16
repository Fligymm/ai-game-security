# P0-C：旧模型 tiled 特征与 QC 结果

日期：2026-11-16  
状态：**descriptive pilot only；未训练分类器；未扩数据**

目的：在默认回退 old 后，用**同一 H/B session、同一 3×3/720 tiling**重新做
P0-C 描述性特征和 QC，避免继续使用 new 模型的 body/head 异常结果。

---

## 1. 输入

```text
H  runs/eval/anticheat_cv_offline/p0b_human_20261116_152512_v0_tiled
B  runs/eval/anticheat_cv_offline/p0b_game_bot_20261116_152746_v0_tiled
```

模型：

```text
runs/detect/cs2_detection_v2/weights/best.onnx
```

配置：

```text
dry_run=true
real_control=false
apply_mouse=false
tile_size=720
grid=3
conf=0.35
iou=0.5
```

特征输出：

```text
runs/eval/anticheat_p0c/pilot_old_tiled_v1/
├── frames.csv
├── session_summary.csv
├── summary.json
└── qc/
    ├── contact_sheet_human.jpg
    ├── contact_sheet_game_bot.jpg
    ├── qc_samples_human.json
    └── qc_samples_game_bot.json
```

---

## 2. old vs new 汇总

| 指标 | old H | old B | new H | new B |
|---|---:|---:|---:|---:|
| detection frame ratio | 36.7% | 35.6% | 47.3% | 68.5% |
| selected frame ratio | 30.7% | 28.8% | 41.8% | 55.3% |
| selected head / body | 132 / 360 | 129 / 344 | 2 / 669 | 6 / 902 |
| unique selected tracks | 54 | 67 | 63 | 82 |
| track switches | 66 | 75 | 82 | 115 |
| acquisition episodes | 93 | 89 | 122 | 154 |
| mean episode duration | 0.157 s | 0.156 s | 0.167 s | 0.177 s |
| mean offset | 80.7 px | 106.8 px | 726.2 px | 653.0 px |
| median offset | n/a | n/a | 913.9 px | 889.6 px |

关键变化：

- old 的检测/选中覆盖低于 new，但 **head/body 选中比例恢复**（约 27% head）；
- old 的 offset 明显更小（约 81/107 px），new 则出现 650–900 px 的大偏移；
- old 仍然有 track 碎片化：H 93 个 episode、B 89 个；track switch H 66、B 75；
- 新旧都不能直接做 H/B 行为分类。

### 2.1 track switch 类型（old）

| 指标 | H | B |
|---|---:|---:|
| switches | 66 | 75 |
| 切换框 IoU≥0.3（疑似 ID churn） | 3 | 3 |
| 切换框 IoU<0.3（目标消失/重捕获或切换） | 63 | 72 |
| 切换框 IoU 中位数 | 0.0 | 0.0 |

这说明大多数切换不是同一框的 ID 抖动，而更可能是目标消失后重新捕获、
目标切换或误报。当前 track ID 仍不适合直接解释为“目标切换行为”。

---

## 3. QC 可视化

已生成 old 模型 contact sheets：

- [`contact_sheet_human.jpg`](../../runs/eval/anticheat_p0c/pilot_old_tiled_v1/qc/contact_sheet_human.jpg)
- [`contact_sheet_game_bot.jpg`](../../runs/eval/anticheat_p0c/pilot_old_tiled_v1/qc/contact_sheet_game_bot.jpg)

每张 20 帧，包含：

```text
检测框（head/body/置信度/track id）
selected 框（黄色粗框）
frame / capture_time / selected class / track id / switch
```

需要人工确认：

1. selected box 是否覆盖真实目标；
2. head/body 框是否存在明显误报；
3. track switch 是目标切换、重捕获，还是检测抖动；
4. old 的 head 检测是否真实可用。

Agent 无法读取图像，因此这一步不能由我代替。

---

## 4. 当前判断

### 可以保留

- old 模型作为 P0-C 默认；
- old 的 head/body 比例明显比 new 更合理；
- 3×3 tiling 是必要的，否则全帧直接推理仍会严重漏检；
- old offset 更小，说明 new 的大偏移结果不应作为行为特征。

### 仍然不能做

- H/B 分类；
- 把 track switch 当作目标切换；
- 把 old/new 的 offset 差异直接解释为作弊行为；
- 用 1 个 H + 1 个 B session 做统计结论。

### 仍需解决

- track run 仍然很短（旧模型 H/B episode 93/89）；
- 目标消失/重捕获与真实目标切换未区分；
- selected target 的真实性未人工复核；
- head 检测虽然恢复，但 head/body 的标注/框质量仍需确认。

---

## 5. 下一步

1. 人工查看 old contact sheets；
2. 若 selected box 大多正确：
   - 先改跟踪/目标级 episode 提取，而不是扩数据；
3. 若 selected box 明显误报或目标消失频繁：
   - 再考虑定向采集/标注；
4. 每类至少 3 个独立 session 后，才做 H/B 描述统计；
5. 仍不训练分类器。

当前结论：

> old 模型使 P0-C 从“head 塌缩”恢复为可分析的 head/body 混合结果；
> 但 track 碎片化和目标身份仍需 QC，暂不适合训练行为分类器。