# P0-C：微调前后模型在 H/B POV 上的对比

日期：2026-11-16  
状态：**descriptive comparison；项目所有者已决定把默认模型回退到 old；未重训**

---

## 1. 目的

用户观察到 P0-C tiled 结果中 head 检测异常少。为判断是“模型文件问题”还是
“模型在 POV 域的取舍”，用微调前的 ONNX 在**同一 H/B session、同一 tiling 配置**
上重新跑一遍。

模型：

```text
new  runs/detect/cs2_multitarget_ft_v1/weights/best.onnx
old  runs/detect/cs2_detection_v2/weights/best.onnx
```

相同配置：

```text
conf=0.35
iou=0.5
tile_size=720
grid=3
dry_run=true
real_control=false
apply_mouse=false
```

---

## 2. 结果

### H session

| 指标 | new | old |
|---|---:|---:|
| frames | 1,604 | 1,604 |
| 有检测帧 | 759 | 588 |
| 选中帧 | 671 | 492 |
| head detections | **3** | **183** |
| body detections | 1,025 | 536 |
| selected head | **2** | **132** |
| selected body | 669 | 360 |
| mean head confidence | 0.393 | 0.604 |
| mean body confidence | 0.461 | 0.746 |
| CSV rows | 671 | 492 |

### B session

| 指标 | new | old |
|---|---:|---:|
| frames | 1,641 | 1,641 |
| 有检测帧 | 1,124 | 584 |
| 选中帧 | 908 | 473 |
| head detections | **7** | **185** |
| body detections | 2,400 | 565 |
| selected head | **6** | **129** |
| selected body | 902 | 344 |
| mean head confidence | 0.453 | 0.706 |
| mean body confidence | 0.485 | 0.749 |
| CSV rows | 908 | 473 |

---

## 3. 解释

### 3.1 不是“旧模型全面更好”

新模型：

- 检测帧更多；
- body 检测/选中更多；
- 在原始 90 帧 320 ROI 检测测试上，head mAP 从 0.745 提升到 0.922
  （见 `FINETUNE_EVAL.md`）。

所以不能简单说新模型文件损坏或全面退化。

### 3.2 是明显的“POV/全帧域”差异

在 1920×1080 第一人称视频 + 3×3 tiling 下：

- 新模型几乎不输出 head：H 3 个、B 7 个；
- 旧模型输出 183 / 185 个 head，且置信度更高；
- 新模型把更多目标输出为 body：H 1,025、B 2,400。

这更符合：

> 新模型在 320×320 ROI 的多目标 body/head 数据上微调后，对全帧 POV 小 head
> 的尺度/域适应变差；旧模型对全屏上下文更稳。或者新模型在训练域内 body
> 召回提升，但这种取舍在 POV tiling 域表现为 head 塌缩。

具体原因还需要用同一批目标做逐框对照；但“新模型在 POV 上 head 检测异常”
已经是可重复现象，不是单帧偶然。

### 3.3 不能直接得出

- 不能直接说新模型“坏了”；
- 不能只凭 head 数量判断模型全面优劣；
- 不能把回退默认理解为“新模型文件损坏”；
- 不能用 H/B 的 head/body 比例直接做行为结论。

---

## 4. 结论

**用户的怀疑有依据：在 H/B POV 上，微调后的新模型出现明显 head 塌缩，
旧模型检测到的 head 多 25–60 倍，且置信度更高。**

但这不是一个简单的“回滚就解决”的问题：

- 新模型在原 90 帧 320 ROI 测试上 head 指标更高；
- 旧模型在 POV 全帧/tiling 上 head 更稳；
- 两者差异是**域/尺度/训练取舍**，需要进一步定位。

项目所有者已决定将 `run_real.py` 和 C 离线工具的默认权重回退为 old；
新模型保留为候选/对比权重。该回退不改变 new 模型在原 90 帧 ROI 测试上的
历史结论，也不代表 new 文件损坏。

---

## 5. 建议

1. **先做逐框对照**：在同一批 H/B 帧上，把 old/new 的 head/body 框并排渲染，
   检查新模型是否把 head 框预测成 body，或直接漏掉。
2. **在原始 90 帧 320 ROI 测试上复跑 old/new**，确认新模型没有文件/导出问题。
3. **在 POV 上比较 old/new 的 head recall**，不要只看总检测数。
4. 如果确认旧模型更适合 POV，需要由项目所有者决定：
   - 是否把 P0-C 的行为分析统一使用 old model；
   - 是否把 new model 保留为检测基准/主模型，但不用它做 POV 头部分析；
   - 是否需要新的 ROI/尺度适配方案。
5. 回退已执行；在逐框原因定位前，不训练分类器，不再改动权重导出。

---

## 6. 输出

```text
runs/eval/anticheat_cv_offline/p0b_human_20261116_152512_v0_tiled
runs/eval/anticheat_cv_offline/p0b_game_bot_20261116_152746_v0_tiled
```

两份输出均：

```text
dry_run=true
real_control=false
apply_mouse=false
source session/video SHA 关联
```