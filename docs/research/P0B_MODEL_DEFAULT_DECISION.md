# P0-B：模型默认回退与 POV 坍缩分析

日期：2026-11-16  
决策：**将 `run_real.py` 默认权重改为微调前旧模型**  
状态：**局部回退；未重训、未改数据集、未改模型文件**

---

## 1. 变更

```text
deployment default:
  old  runs/detect/cs2_detection_v2/weights/best.onnx
experimental branch:
  experimental/cs2_multitarget_ft_v1  (new model, restricted)
  new  runs/detect/cs2_multitarget_ft_v1/weights/best.onnx
```

代码：

```text
run_real.py: _DEFAULT_WEIGHTS -> cs2_detection_v2/weights/best.onnx
```

新的默认行为：

```powershell
python run_real.py --record-dir runs/captures --record-scene static_target
```

如需微调模型，显式指定：

```powershell
python run_real.py `
  --weights "runs\detect\cs2_multitarget_ft_v1\weights\best.onnx"
```

没有启动 `run_real.py`，没有发送真实输入。

---

## 2. POV 同配置对比

H/B 两个 session、3×3/720 tiling、conf=0.35、iou=0.5：

| 指标 | new | old |
|---|---:|---:|
| H head detections | 3 | 183 |
| H selected head | 2 | 132 |
| H body detections | 1,025 | 536 |
| B head detections | 7 | 185 |
| B selected head | 6 | 129 |
| B body detections | 2,400 | 565 |
| old/new head confidence | lower | higher |

**旧模型在 POV 上 head 检测明显更稳；新模型严重 body 偏置。**

这不是说新模型文件损坏：新模型在原 90 帧 320×320 ROI 测试上 head mAP 仍为 0.922，
高于旧的 0.745。

---

## 3. 旧 v2 训练数据审计

审计对象：

```text
datasets/cs2_custom/train
datasets/cs2_custom/val
runs/detect/cs2_detection_v2/args.yaml
runs/detect/cs2_detection_v2/results.csv
```

### 3.1 数量与标签

| Split | images | labels | boxes | head | body | empty |
|---|---:|---:|---:|---:|---:|---:|
| train | 119 | 119 | 270 | 135 | 135 | 0 |
| val | 30 | 30 | 66 | 33 | 33 | 0 |

结论：

- 图像与标签一一对应，**没有缺标签样本**；
- head/body 类别数量完全平衡（135/135、33/33）；
- 没有空标签；
- 不是“类别权重失衡”或“标签缺失”导致的塌缩。

### 3.2 图像/标签异常

- train 中有 1 张 `525×607` 图像，其余样本为 `2560×1440`；
- val 全部为 `2560×1440`；
- 这是尺度/裁剪不一致，但不是系统性缺失；
- 旧 head 框平均约 1.1% 宽、2.0% 高；body 约 2.7% 宽、9.8% 高。

### 3.3 训练参数

旧 `args.yaml` 关键项：

```text
model          yolov8n.pt
epochs         50
imgsz          640
batch          16
lr0            0.01
mosaic         1.0
scale          0.5
fliplr         0.5
seed           0
```

没有发现缺失的必需训练参数。该模型的 val mAP50 停在约 0.61，并不是一个
在旧数据上 head 指标很高的模型，但它在 POV 上保留了 head 响应。

---

## 4. 用新模型复检旧 v2 数据

在旧 v2 **val** 的 30 张 2560×1440 图像上，用 conf=0.35 做简单 IoU≥0.5 匹配
（描述性，不是官方 mAP）：

| 类别 | old TP / GT | old recall | new TP / GT | new recall |
|---|---:|---:|---:|---:|
| head | 6 / 33 | 0.182 | 0 / 33 | **0.000** |
| body | 26 / 33 | 0.788 | 2 / 33 | **0.061** |

新模型在旧全屏域上几乎完全失效，说明 POV 上的 head 塌缩不是 H/B 视频特有，
而是**新模型对旧全屏/大尺度域的适应显著退化**。

---

## 5. 可能原因

按证据强弱排序：

1. **域/尺度漂移（主因）**  
   新模型只训练 320×320 ROI；旧模型训练 2560×1440 全屏。POV 全帧 + tiling
   后 head 相对尺度/上下文与新训练分布不同。

2. **微调数据规模小且场景窄**  
   新增训练只有 100 帧、2 个 scene；虽然 head/body 平衡，但没有覆盖
   POV 全屏的 head 尺度和遮挡变化。

3. **body 偏置/灾难性遗忘**  
   新模型在 90 帧 ROI 测试上 head 指标更高，但在全屏域几乎不输出 head，
   更像是对训练域 body 上下文的过拟合，而非文件损坏。

4. **旧数据中的单张异常裁剪**  
   1 张 525×607 图片与全屏尺度不一致，可能引入少量尺度噪声，但不足以解释
   25–60 倍差距。

5. **不是类别权重/标签缺失**  
   旧数据 head/body 完全平衡，无空标签、无缺标签；没有证据支持“权重失衡”
   是主因。

---

## 6. 结论

- **回退默认模型是合理的临时措施**：P0-B POV 场景下旧模型 head 检测明显更可靠。
- **新模型不是简单损坏**：它在原 ROI 测试上仍优；问题是 POV/全屏域退化。
- **旧数据没有明显权重失衡或标签缺失**：类别平衡、标签完整；主因更可能是
  域/尺度漂移和微调数据覆盖不足。
- 不重训、不新增数据；先保留旧模型默认，等待进一步决策。

---

## 7. 下一步

1. 在原始 90 帧 320 ROI 测试上复跑 old/new，确认新模型导出和指标仍一致；
2. 对同一批 H/B 帧做 old/new 逐框叠加，确认新模型是漏检 head 还是把 head 判成 body；
3. 决定 P0-C 后续统一使用 old 还是 new，避免混用；
4. 若确需提升 POV head，再考虑针对 POV head 尺度/场景的数据扩展，不在本轮自动进行。

---

## 8. 证据

- [`P0C_MODEL_COMPARISON.md`](P0C_MODEL_COMPARISON.md)
- 旧数据：`datasets/cs2_custom/`
- 旧训练：`runs/detect/cs2_detection_v2/`
- 新模型：`runs/detect/cs2_multitarget_ft_v1/`
- 默认代码：`run_real.py`