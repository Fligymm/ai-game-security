# POV 检测域适应：首轮结果

日期：2026-11-17  
状态：**positive body result；head 未恢复；不宣称全面成功**

---

## 1. 数据与训练

test labels：

```text
80 帧人工复核
149 boxes
head 74 / body 75
empty 13
```

train/val：

```text
train: 240 帧 prelabels
val:    80 帧 prelabels
```

POV 模型：

```text
YOLOv8n
初始化 old best.pt
imgsz 1280
batch 4
epochs 60 (early stop at 33, best epoch 18)
```

运行：

```text
runs/detect/pov_ft_v1-2/
```

---

## 2. Full-frame 1280 test

| 模型 | mAP50 | mAP50-95 | Precision | Recall |
|---|---:|---:|---:|---:|
| old | 0.485 | 0.262 | 0.839 | 0.515 |
| new ROI | 0.022 | 0.016 | 0.132 | 0.033 |
| **POV** | **0.539** | **0.304** | **0.887** | **0.575** |

Per-class：

| 模型 | head mAP50 | head P/R | body mAP50 | body P/R |
|---|---:|---|---:|---|
| old | 0.257 | 0.697 / 0.311 | 0.713 | 0.982 / 0.720 |
| new ROI | 0.000 | 0.000 / 0.000 | 0.045 | 0.263 / 0.067 |
| POV | 0.254 | 0.774 / 0.324 | **0.825** | **1.000 / 0.827** |

结论：

- POV 模型整体 mAP50 高于 old，主要来自 **body**；
- head mAP50 与 old 基本持平，没有恢复；
- ROI new 在 POV 上仍然完全失效。

---

## 3. Tiled 3×3 / 720 micro P/R

| 模型 | head P / R | body P / R |
|---|---|---|
| old | 0.696 / **0.432** | 0.952 / 0.787 |
| new ROI | 0.000 / 0.000 | 0.216 / 0.280 |
| POV | 0.778 / 0.284 | **0.940 / 0.840** |
| **hybrid（old head + POV body）** | **0.696 / 0.432** | **0.940 / 0.840** |

hybrid 是当前最好的组合：

```text
head: old model
body: POV model
```

它保留了 old 的 head 能力，同时获得 POV 的 body 提升。

---

## 4. 结论

### 可以主张

- POV 微调可以显著提升 **body** 检测；
- ROI new 模型在 POV 上完全不可用；
- 类别级模型路由（old head + POV body）是有效的工程方案；
- 检测方向确实有可测量的正结果，不是纯负结果。

### 不能主张

- POV 模型恢复了 head 检测；
- POV 模型全面优于 old；
- 已经达到论文级完整系统；
- 跨地图泛化已经验证。

### 当前瓶颈

```text
head 训练标签不足
train/val 只有 prelabels
test 只有 80 帧
```

POV head 没有提升，最可能原因是训练集中 head 监督不足/不准确，而不是架构问题。

---

## 5. 论文可行性判断

### 可以写的应用论文

> POV 游戏屏幕目标检测的类别级域适应：body 提升与 head 保留

贡献：

1. ROI→POV 域漂移量化；
2. POV 微调提升 body；
3. old head + POV body 的类别路由；
4. tiled/full-frame 对比；
5. 坦诚报告 head 未恢复。

这比纯 negative result 更有正结果，但对“head 检测”主张仍有限。

### 若要更强论文

需要：

1. 人工复核 train/val（至少 64–100 帧）；
2. 增加 head 训练样本；
3. 重新训练 head 或使用 head-aware sampling；
4. 在 test 上重新评估；
5. 再做 cross-map（aim_botz）测试。

---

## 6. 输出

```text
runs/detect/pov_ft_v1-2/
runs/eval/pov_eval_test_all.json
runs/eval/pov_tiled_eval_test.json
runs/eval/pov_tiled_eval_hybrid.json
```

工具：

- `tools/train_pov_detector.py`
- `tools/eval_pov_detector.py`
- `tools/eval_pov_tiled.py`

---

## 7. 当前决定

```text
不覆盖 old deployment default
POV 模型仅实验
不宣称反作弊检测
不把 body 提升写成 head 恢复
```

下一步二选一：

1. **先写 body/类别路由应用论文**；
2. **补 train/val head 标签，再冲 head 正结果**。

从“投入有回报”角度，方案 1 已具备正结果；方案 2 上限更高但需要额外标注。