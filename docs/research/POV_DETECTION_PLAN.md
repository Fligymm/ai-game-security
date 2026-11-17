# POV 目标检测域适应计划

日期：2026-11-17  
方向：从 negative/benchmark 论文转向**可产生正结果的检测论文**  
状态：**预标注数据集已生成；等待人工标注复核；尚未训练**

---

## 1. 研究问题

ROI 微调模型在 320×320 同域数据上更强，但在 1920×1080 第一人称 tiled
场景中 head 检测塌缩：

```text
old POV head: 183 / 185
new POV head: 3 / 7
new ROI mAP50: 0.922
old ROI mAP50: 0.745
```

问题：

> 能否用少量 POV 标注 + 轻量模型适配，在保持实时性的同时恢复 POV head 检测？

这不是反作弊分类论文，而是：

> 游戏屏幕第一人称目标检测的域适应与轻量模型评估

---

## 2. 论文候选标题

> *Closing the Domain Gap: Multi-Scale Tiling and POV Adaptation for Lightweight Game-Screen Target Detection*

中文：

> 面向第一人称游戏屏幕的轻量目标检测域适应：多尺度切图与 POV 微调

---

## 3. 数据

### 3.1 Session split

使用 dust2 + nuke 的 20 个 60s session；aim_botz 6H 保留为 cross-map。

```text
train: 12 sessions（dust2 3H/3B + nuke 3H/3B）
val:    4 sessions（dust2 1H/1B + nuke 1H/1B）
test:   4 sessions（dust2 1H/1B + nuke 1H/1B）
```

配置：

```text
configs/pov_detection_sessions.json
```

### 3.2 预标注数据

```text
datasets/pov_detection_v1/
├── images/train (240)
├── images/val (80)
├── images/test (80)
├── labels/...
├── manifest.csv
├── data.yaml
└── DATASET_META.json
```

每 session 20 帧，共 400 帧。

预标注来源：old 模型 3×3 tiled 输出，conf≥0.35。

当前标签统计：

```text
总 boxes 415
head 113
body 302
```

**这些是 prelabels，不是人工真值；训练前必须复核。**

### 3.3 复核建议

最低要求：

- 100% test 集（80 帧）；
- 20% train/val 抽查（约 64 帧）；
- 重点检查 head 框、body 误报、空帧。

复核工具：

- 可用 LabelImg / CVAT / Label Studio；
- 输出 YOLO 格式；
- 保留 `manifest.csv` 的 session/split 映射。

预标注 contact sheet：

```text
datasets/pov_detection_v1/review_contact_sheet.jpg
```

完整复核流程见：

- [`POV_LABEL_REVIEW_PROCEDURE.md`](POV_LABEL_REVIEW_PROCEDURE.md)
- Label Studio 配置：`configs/labelstudio_pov.xml`
- JSON → YOLO 转换：`tools/labelstudio_to_yolo.py`

---

## 4. 训练计划

基线：

```text
old  best.pt
new  best.pt（ROI 微调）
```

新模型：

```text
YOLOv8n
初始化：old best.pt
输入：POV 全帧，imgsz=1280（如显存不足降到 1024）
epochs：50–80
batch：4–8
mosaic：0.3–0.5
scale：0.2–0.4
```

评估：

1. full-frame inference；
2. 3×3 tiled inference；
3. head/body mAP50、recall、precision；
4. per-map（dust2/nuke）；
5. held-out test session；
6. cross-map aim_botz 6H 只做推理检查，不训练。

---

## 5. Go/no-go

### 正结果门槛

```text
POV model mAP50 > old model
head recall 明显 > old model
cross-map 下降可控
推理仍可实时（>=20 FPS 或接近）
```

建议门槛：

```text
head recall +0.15 以上
mAP50 +0.10 以上
```

### 不达标

- 不继续堆训练；
- 退回 benchmark/negative paper；
- 或只报告“ROI 微调域漂移”的短论文。

---

## 6. 预期贡献

1. 一个可复现的 POV 游戏屏幕检测 benchmark；
2. ROI→POV 域漂移的量化分析；
3. tiling + POV adaptation 的轻量方案；
4. 跨地图/跨 session 评估；
5. 部署建议：什么时候用 ROI 模型、什么时候用 POV 模型。

---

## 7. 目标期刊

优先级：

1. IEEE Access；
2. Entertainment Computing；
3. Journal of Real-Time Image Processing；
4. Multimedia Tools and Applications；
5. IEEE Transactions on Games（stretch）。

---

## 8. 当前需要人工完成

```text
[ ] 复核 test 80 帧
[ ] 抽查 train/val 64 帧
[ ] 修正 head/body 框
[ ] 确认空帧
[ ] 导出 YOLO 标签
```

完成后再训练；当前没有开始训练，也没有修改部署模型。

---

## 9. 不做什么

- 不覆盖 old deployment default；
- 不启用 new 模型作为默认；
- 不把 prelabels 当人工真值；
- 不宣称反作弊检测；
- 不在未复核 test 集上报告结果。