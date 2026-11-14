# CS2 感知改进任务书 v1

> 版本：v1.0（2026-11-14）  
> 执行人：项目所有者 + Agent  
> 目的：基于已完成的 90 帧 pilot 标注和 ONNX 基线，先做**头部漏检错误分析**，再决定是否扩样、调整推理分辨率或重训；不直接拿 test 调参。  
> 当前状态：Pilot 采集、90 帧标注、ONNX 外部测试均已完成；43 个漏检头部已人工复核，P2-02 汇总完成；下一步是 P2-03 方向决策（见 `HARD_EXAMPLE_ANALYSIS.md`）。

---

## 1. 当前基线（不要重复跑）

| 项目 | 结果 |
|---|---|
| Pilot | 3 场景，53,436 帧，29.74 分钟 |
| 标注 | 90 帧，280 框，6 空图 |
| 模型 | `runs/detect/cs2_detection_v2/weights/best.onnx` |
| 测试集 | `runs/pilot_20261114_1920x1080/annotation` |
| mAP50 | 0.785 |
| mAP50-95 | 0.314 |
| conf=0.35 全类 P / R / F1 | 0.910 / 0.718 / 0.802 |
| conf=0.35 head-only P / R / F1 | 0.860 / 0.695 / 0.769 |
| 空图误报 | 6 张中 0 张 |

数据边界：

- 90 帧是**小样本外部测试**，不是整体反作弊准确率；
- test 帧不参与训练；
- `static_target` / `slow_strafe` 的 head-only 召回只有 0.574 / 0.596，是当前瓶颈；
- 现有真实 CS2 自动吸附链路不改；本轮只做感知分析和数据改进。

证据：

- [`PERCEPTION_EVAL.md`](../runs/pilot_20261114_1920x1080/PERCEPTION_EVAL.md)
- [`eval_report.json`](../runs/eval/pilot_v0_onnx/eval_report.json)

---

## 2. 任务总览

| ID | 任务 | Owner | 状态 | 验收 |
|---|---|---|---|---|
| P2-01 | 43 个漏检头部的人工分型 | 项目所有者 | **Done** | `review_final.csv` 43/43，`review_summary.json` `ok=true` |
| P2-02 | 分型汇总与干预建议 | Agent | **Done** | [HARD_EXAMPLE_ANALYSIS.md](../runs/pilot_20261114_1920x1080/hard_examples/HARD_EXAMPLE_ANALYSIS.md) |
| P2-03 | 选择下一步：分辨率实验 / 扩样 / 重训 | 项目所有者 + Agent | **现在做** | 只选一个方向，写清验收和预算 |
| P2-04 | 若重训：固定切分与对比 | Agent | 条件触发 | test 不参与训练，指标不退化的前提下 head 指标提升 |
| P2-05 | 跟踪/控制指标（ID switch、丢失率） | Agent | 后续 | 固定 session-level 测试，单独报告 |

---

## 3. P2-01：人工复核 43 个漏检头部（现在做）

### 3.1 输入

```text
runs/pilot_20261114_1920x1080/hard_examples/
├── contact_sheets/       # 7 张总览图，最多 8 个裁剪/张
├── crops/                # 43 个放大裁剪
├── review.csv            # 需要你填的表
├── summary.json          # 机器汇总
└── README.md             # 简版说明
```

先打开：

- [`hard_examples/README.md`](../runs/pilot_20261114_1920x1080/hard_examples/README.md)
- [`hard_examples/contact_sheets/`](../runs/pilot_20261114_1920x1080/hard_examples/contact_sheets)
- [`hard_examples/review.csv`](../runs/pilot_20261114_1920x1080/hard_examples/review.csv)

### 3.2 怎么做

1. 按 `contact_sheets/` 的 7 张图逐张看；每张图左上角有 `#NNN`，对应 `review.csv` 的 `index`。
2. 对每个漏检，在 `review.csv` 的 `failure_type` 列填**一个**值：

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

3. `notes` 写一句原因，例如“头部只露 5px”“被队友挡住”“框偏到肩膀”“画面本身很糊”。
4. 允许参考以下字段，但不要只看字段下结论：

| 字段 | 含义 |
|---|---|
| `area_px` | GT 头框面积，越小越可能是小目标 |
| `nearest_pred_iou` | 最近的同类预测与 GT 的 IoU；0.3–0.5 更像定位偏移，接近 0 更像完全漏检 |
| `nearest_pred_conf` | 最近同类预测的置信度 |
| `laplacian_var` | 清晰度参考；越低越可能模糊 |
| `std_luma` | 对比度参考 |

5. 不要修改 `crops/`、`contact_sheets/` 或原始标签；只填 `failure_type` 和 `notes`。
6. 保存为 UTF-8 CSV。

### 3.3 判定建议

- `small`：头部像素面积明显小，模型输入 640 下细节不足；
- `occluded`：被墙、队友、武器、HUD 或自身手臂遮挡；
- `motion_blur`：fast/slow 移动导致头部拖影；
- `low_contrast`：头与背景颜色/亮度接近；
- `label_boundary`：头贴着 ROI 边缘或框本身跨边界；
- `model_localization`：模型有框但位置偏，IoU < 0.5；
- `clear_miss`：**目标在 4× 裁剪中清晰、无明显遮挡/模糊/低对比/边界问题，模型就是没检测到**；这是“明显应该检测到却漏检”的类别，单独统计，不能塞进 `other`；
- `other`：确实无法归类，或同时存在多种原因无法判断主因；在 notes 说明。

判定顺序：

```text
先看有没有客观困难：
  小目标 -> small
  遮挡 -> occluded
  拖影 -> motion_blur
  低对比 -> low_contrast
  贴 ROI 边缘 -> label_boundary
  有框但偏 -> model_localization
以上都不成立，且肉眼清楚 -> clear_miss
实在判断不了 -> other
```

> `clear_miss` 不是垃圾桶，也不是“模型定位偏”；它是明确的模型漏检，P2-02 会优先看。`other` 允许，但应尽量少；如果 `other` 超过 4 个，P2-02 会先复查。

### 3.3.1 本次 43 行的实际处理建议

当前 `review.csv` 已由项目所有者填完 43 行，但原表使用了 12 个 `other`。按备注可以明确分流：

- 11 行 `other` + `notes="漏检"` → `clear_miss`；
- 1 行 `other` + `notes="框偏到肩膀"`（#012）→ `model_localization`；
- #000 `occluded` + `notes="贴着 ROI 边缘"` → `label_boundary`。

已确认并生成 [`review_final.csv`](../runs/pilot_20261114_1920x1080/hard_examples/review_final.csv)；`review.reclassified.csv` 是建议过程副本，原 `review.csv` 保留不动。最终分型为：

```text
small = 23
clear_miss = 11
model_localization = 3
low_contrast = 3
label_boundary = 1
motion_blur = 1
occluded = 1
other = 0
```

这说明“明显应检测到却漏检”不是个别现象：**11/43 = 25.6%**，且 slow_strafe 7 个、static_target 4 个、fast 0 个。P2-02 会把它作为最高优先级模型错误。

### 3.4 验收标准

P2-01 通过必须同时满足：

- `review.csv` 仍有 43 行，`index` 0–42 不缺；
- 43/43 行 `failure_type` 非空；
- 每行 `failure_type` 属于上面 8 个值；
- `other` ≤ 4 行，且每行有 `notes`；
- 所有 `model_localization` 行有 notes 说明“框偏在哪”；
- `clear_miss` 行不限数量，但 notes 要写“清晰/无遮挡/无明显模糊”等判定依据；
- 运行汇总命令返回 `ok=true`：

```powershell
cd D:\AI_Security\ai-game-security

.\.venv\Scripts\python.exe tools\summarize_hard_examples.py `
  --review "runs\pilot_20261114_1920x1080\hard_examples\review_final.csv" `
  --output "runs\pilot_20261114_1920x1080\hard_examples\review_summary.json"
```

期望：

```json
{
  "ok": true,
  "total": 43,
  "reviewed": 43,
  "missing": [],
  "invalid": []
}
```

### 3.5 时间盒

- 43 个裁剪，建议 **30–60 分钟**；
- 一次看不完可以分两次，但不要隔太久导致标准漂移；
- 先看完 7 张 contact sheet，再统一填表，比逐张切换更快。

### 3.6 明确不要做

- 不要重训模型；
- 不要用这 90 帧调 `conf` / `iou` / `imgsz` 后再报告同一 test；
- 不要改 `annotation/labels/` 来“让模型看起来更好”；
- 不要把漏检直接说成“数据错误”；先分型。

---

## 4. P2-02：Agent 汇总与干预建议（你填完后我做）

输入：`review_summary.json` + `review_final.csv` + 43 个裁剪。

输出：

```text
runs/pilot_20261114_1920x1080/hard_examples/
├── HARD_EXAMPLE_ANALYSIS.md
├── review_summary.json
├── contact_sheets/            # 7 张总览图
└── crops/                    # 43 个放大裁剪
```

我会给出：

1. 按 scene / failure_type 的计数表和占比；
2. 每个类型的 2–3 个代表例子；
3. 归因判断：数据问题、标注问题、模型容量/输入分辨率问题，还是阈值问题；
4. 干预矩阵：

| 观察 | 优先动作 | 不优先 |
|---|---|---|
| 主要是 small | 试 `imgsz=960/1280`；扩小目标样本 | 先重训 |
| 主要是 occluded | 扩遮挡样本；接受部分不可见 | 盲目降 conf |
| 主要是 motion_blur | 扩 fast 样本；检查快门/采集 | 只改模型 |
| 主要是 model_localization | 检查标注框一致性；后处理/NMS | 直接加数据 |
| 主要是 clear_miss | 作为最高优先级错误集：检查是否系统性（场景/尺度/背景），再考虑难例挖掘/重训 | 归为 other 或不处理 |
| 主要是 label_boundary | 修 ROI/标注规则；剔除边界样本 | 重训 |
| 主要是 low_contrast | 数据增强/扩样 | 只调阈值 |

验收：

- 43 个全部有类型；
- `clear_miss` 单独列出，并判断是否集中在 static/slow、某个背景或某个尺度；
- 每类至少 2 个代表例子（若数量允许）；
- 给出一个**首选动作**和一个**备选动作**；
- 明确“不在 test 上调参”；
- 不把 90 帧结论写成整体准确率。

### 4.1 已完成结果

最终分型（`review_final.csv`）：

```text
small              23 / 43 = 53.5%
clear_miss         11 / 43 = 25.6%
model_localization  3 / 43 = 7.0%
low_contrast        3 / 43 = 7.0%
label_boundary      1
motion_blur         1
occluded            1
other               0
```

关键结论：

- `clear_miss` 的框中位面积约 1160 px²，`conf=0.35` 下全部无同框预测；
- 11 个 clear_miss 中 **9 个发生在 2–4 个头的多目标帧**；
- 旧训练集 86.6% 是单目标，pilot test 有 48.8% 多目标帧；
- 降到 `conf=0.001` 后只有 5/11 有几何候选，置信度仅 0.002–0.007，不能靠降阈值解决；
- 结论：主线是补多目标数据，不是降阈值或只调 `imgsz`。

完整分析：[`HARD_EXAMPLE_ANALYSIS.md`](../runs/pilot_20261114_1920x1080/hard_examples/HARD_EXAMPLE_ANALYSIS.md)。

---

## 5. P2-03：下一步方向选择（P2-02 之后）

只选一个主方向，不要同时做三件事。

### 方向 A：推理分辨率实验（最轻，先做）

在**不重训**的前提下，用同一 test 比较：

```text
imgsz = 640（当前）
imgsz = 960
imgsz = 1280
```

只看：

- head mAP50 / mAP50-95；
- head-only P/R @ conf=0.35；
- static/slow 的 head recall；
- ONNX 单图推理延迟。

验收：

- 三种分辨率同一 test、同一 conf、同一 IoU；
- 输出表格和延迟；
- 若 960/1280 没有稳定提升，不进入重训；
- 延迟超过 30fps 预算（单帧推理 > 10ms 仅作预警，最终看端到端）要记录。

### 方向 B：扩样（数据侧）

适用：分型显示 small/occluded/motion_blur 为主。

最低验收：

- 新增 ≥ 150 帧人工标注（建议 3 个新 session 或补难例）；
- 类别仍为 `enemy_head` / `enemy_body`；
- 空图/遮挡图有记录；
- 新数据不进入 test；
- 数据质量检查通过；
- 新数据按 session 分组切分，不能同 session 泄漏。

### 方向 C：重训/微调（最重）

只有 A/B 有明确证据时才做。

前置条件：

- 固定 train/val/test；
- test 不参与训练、不参与调参；
- 记录数据版本、模型 hash、训练参数；
- 保留当前 `best.onnx` 作为对照。

暂定验收（90 帧 test，方向性指标）：

- head mAP50 相对当前 0.745 提升 ≥ 0.03 绝对值；
- 或 head-only recall @0.35 相对 0.695 提升 ≥ 0.05 绝对值；
- body mAP50 下降 ≤ 0.02；
- fast mAP50 下降 ≤ 0.02；
- 6 张空图误报不增加；
- 推理延迟不超出 30fps 预算；
- 报告必须同时给出新旧模型对照，不只报新模型。

> 90 帧样本小，以上是方向性门槛，不是统计显著性结论。若指标接近门槛，先扩 test 再决定。

---

## 6. 通用验收与边界

### 6.1 数据

- 原始 session 不修改；派生标注/裁剪放 `runs/.../annotation` 或 `hard_examples`；
- 不混入旧 2560×1440 目录的数据；
- 任何新标注都要保留 `manifest.json` 来源、session、frame_id；
- 空图要保留，不能为了“好看”删除。

### 6.2 评估

- mAP 用 `conf=0.001`；部署 P/R 用 `conf=0.35`；
- 匹配 IoU 固定 0.5；
- 每次报告写清模型、imgsz、conf、test 版本；
- 不用 test 调阈值；
- 不把单帧召回等同于整段吸附成功率；
- 不写“99.2%”或“整体反作弊准确率”。

### 6.3 安全

- 不改 `ChainedBackend`、CSV `flush()`、Kill Switch、`--apply-mouse` 默认安全语义；
- 不硬编码 `apply_mouse=False`；
- 不在没有 ESC/F12 的情况下跑真实控制；
- 本轮错误分析不需要启动游戏、不需要真实鼠标。

---

## 7. 现在只做 P2-03：多目标扩样

> 具体采集、抽样、标注、转换、验收命令见 [`MULTITARGET_DATA_TASKBOOK.md`](MULTITARGET_DATA_TASKBOOK.md)。

P2-01 的分型已经确认，P2-02 的结论是：

> **首选方向 B：补多目标数据。**  
> 不是降 `conf`，不是只调 `imgsz`，也不是直接拿旧数据重训。

### 7.1 你下一步要做什么

1. **确认采用方向 B**，并新建一个数据目录，例如：

   ```text
   runs/pilot_20261115_multitarget/
   ```

2. 按 [`CS2_PILOT_TASKBOOK.md`](CS2_PILOT_TASKBOOK.md) 的采集流程，采 **3 个新 session**：
   - `static_target`
   - `slow_strafe`
   - `fast_strafe`
   - 每个约 10 分钟；
   - 尽量让画面里同时出现 **2–4 个可见头部**，而不是只有 1 个目标。

3. 从新 captures 中抽 **150 帧**做人工标注：
   - ≥60 帧含 2 个及以上 head；
   - ≥20 张空图；
   - 3 个 scene 都要覆盖；
   - 90 帧 pilot test **保持不动**，不加入训练。

4. 标注规则不变：
   - `enemy_head=0`、`enemy_body=1`；
   - 紧凑框；
   - 不标 HUD/准星；
   - 空图要 Submit，不要 Skip。

### 7.2 验收标准

- 新数据 150 帧，标签完整；
- ≥60 帧多目标，≥20 帧空图；
- 按 session 分组切分，不能同 session 泄漏；
- 90 帧 pilot test 不参与训练/调参；
- 训练前先跑数据质量检查；
- 训练后与当前 `best.onnx` 在同一 90 帧 test 对比。

### 7.3 如果暂时不想采 150 帧

先做 **30 帧多目标验证集**：

- 选 1 个新 session；
- 包含至少 20 帧 2+ 头；
- 用当前模型评估，确认“多目标欠检出”是否复现；
- 如果复现，再扩到 150 帧；如果不复现，先复查标注/场景差异。

### 7.4 现在不要做

- 不要重训当前 120 张旧数据；
- 不要用 90 帧 test 调 `conf` / `imgsz`；
- 不要把 `clear_miss` 重新塞回 `other`；
- 不要为了凑多目标帧，把同一帧重复采样。