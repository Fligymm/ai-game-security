# P0-C 目标与跟踪 QC 流程

版本：v1.0  
日期：2026-11-16  
适用：old 模型 `cs2_detection_v2` 的 H/B P0-C tiled 输出  
状态：**人工复核流程；不是自动分类结论**

---

## 1. 目的

在进入 P0-C 特征统计或分类器训练前，确认：

1. selected box 是否覆盖真实目标；
2. body/head 检测是否存在明显误报；
3. track ID 的切换是目标切换、重捕获，还是检测抖动；
4. head 是真的不可见，还是被漏检；
5. 当前数据是“目标覆盖不足”，还是“tracker 不稳定”。

本流程的输出只用于判断数据/跟踪质量，不用于证明作弊行为。

---

## 2. 输入

```text
H session:
  runs/captures/p0b_pilot/p0b_human_20261116_152512
  runs/eval/anticheat_cv_offline/p0b_human_20261116_152512_v0_tiled

B session:
  runs/captures/p0b_pilot/p0b_game_bot_20261116_152746
  runs/eval/anticheat_cv_offline/p0b_game_bot_20261116_152746_v0_tiled

QC contact sheets:
  runs/eval/anticheat_p0c/pilot_old_tiled_v1/qc/contact_sheet_human.jpg
  runs/eval/anticheat_p0c/pilot_old_tiled_v1/qc/contact_sheet_game_bot.jpg

QC samples:
  runs/eval/anticheat_p0c/pilot_old_tiled_v1/qc/qc_samples_human.json
  runs/eval/anticheat_p0c/pilot_old_tiled_v1/qc/qc_samples_game_bot.json
```

每个 contact sheet 当前包含 20 个 selected/head/switch 样本，用于第一轮筛查；
还需要补充负样本和连续帧检查。

---

## 3. 角色

```text
Reviewer A  主审：逐帧检查 H/B 样本，填写 QC 表
Reviewer B  复核：盲审至少 20% 样本，处理分歧
Owner       裁决：是否修 tracker、是否扩数据、是否继续 P0-C
```

建议 Reviewer A 和 B 不同人；如果只有一人，必须在报告中标注“single reviewer”。

---

## 4. 抽样方案

### 4.1 第一轮：contact sheet 全量

检查已有的 20 帧/session：

- H：`contact_sheet_human.jpg`
- B：`contact_sheet_game_bot.jpg`

目的：快速判断整体是否可用，找出需要回看视频的帧。

### 4.2 第二轮：分层补样

每个 session 至少补到 **30–40 帧**，覆盖：

| 类型 | 目的 |
|---|---|
| 有检测、有 selected | 正常目标 |
| 有检测、无 selected | 选择器/输出门问题 |
| 无检测、画面中目标可见 | 漏检 |
| 无检测、无目标 | 背景/空场景 |
| track switch 前后各 3 帧 | 判断切换类型 |
| 短 episode（≤2 帧） | ID 碎片/误报 |
| head selected | head 质量 |
| body selected | body 质量 |
| offset 很大 | 远目标/误锁定 |

补样帧可以从 `inference_frames.jsonl` 的 `frame_index` 选取，使用源视频逐帧查看。

### 4.3 第三轮：连续片段

对每个被标记为 `TRACK_BREAK` 或 `WRONG_TARGET` 的帧：

- 向前看 5–10 帧；
- 向后看 5–10 帧；
- 判断目标是否真实消失、被遮挡、换目标，还是 tracker 丢 ID。

不要把单帧判断当作跟踪结论。

---

## 5. 逐帧判定字段

建议使用 [`P0C_QC_TEMPLATE.csv`](P0C_QC_TEMPLATE.csv) 记录。

| 字段 | 取值/说明 |
|---|---|
| `session_id` | 来源 session |
| `agent_type` | human / game_bot |
| `frame_index` | 视频帧号 |
| `capture_time_s` | 来自 events 的时间 |
| `target_present` | yes / no / uncertain |
| `visible_class` | head / body / both / other / none |
| `det_box_correct` | yes / partial / no / no_detection |
| `selected_box_correct` | yes / wrong_target / false_positive / none |
| `head_missed` | yes / no / n/a |
| `body_false_positive` | yes / no / uncertain |
| `track_continuity` | same / switch / reacquire / break / n/a |
| `occlusion` | none / partial / full |
| `ui_overlay` | yes / no |
| `decision` | GOOD / BODY_ONLY / HEAD_MISSED / FALSE_POSITIVE / WRONG_TARGET / TRACK_BREAK / TARGET_ABSENT / UNCERTAIN |
| `notes` | 具体说明 |
| `reviewer` | 匿名 ID |
| `review_date` | YYYY-MM-DD |

判定规则：

- `GOOD`：目标存在，box 覆盖目标，selected 正确；
- `BODY_ONLY`：目标可见但只选了 body，head 未选；
- `HEAD_MISSED`：head 明确可见但无 head 检测/选中；
- `FALSE_POSITIVE`：selected 框没有真实目标；
- `WRONG_TARGET`：selected 框指向了错误目标；
- `TRACK_BREAK`：同一目标 track ID 中断/重捕获；
- `TARGET_ABSENT`：画面无目标或目标不可见；
- `UNCERTAIN`：单帧无法判断，必须看连续帧。

---

## 6. 操作步骤

### Step 0：冻结输入

确认使用：

```text
run_real.py / C 默认 old
session timebase PASS
source video SHA 与 inference_meta 一致
dry_run=true
real_control=false
```

不要在这轮改动模型、tracker 或数据。

### Step 1：看整体 contact sheet

- 先快速浏览 20 帧 H/B；
- 标记明显误报、错误目标、head 可见但未选、目标不可见的帧；
- 不急着逐帧精确判定。

### Step 2：逐帧填写 QC 表

对每个样本：

1. 找到 `frame_index`/`capture_time_s`；
2. 打开对应源视频帧；
3. 对照检测框/selected 框；
4. 填写字段；
5. 有疑问的写 `UNCERTAIN`，不要猜。

### Step 3：看连续帧

对以下情况必须回看 ±5–10 帧：

- `TRACK_BREAK`
- `WRONG_TARGET`
- `head_missed=yes`
- 短 episode
- offset 异常大

### Step 4：复核

Reviewer B 盲审至少：

```text
H: 10 帧
B: 10 帧
```

比较 A/B 的 `decision`：

- 一致：通过；
- 不一致：回看连续帧，由 Owner 裁决；
- 记录分歧，不删除原始记录。

### Step 5：汇总指标

按 session 统计：

```text
target_present_rate
selected_precision（人工判定）
false_positive_rate
wrong_target_rate
head_missed_rate
track_break_rate
same_target_continuity_rate
median_episode_duration
```

这些是人工 QC 统计，不是模型 mAP，也不是作弊检测准确率。

---

## 7. 质量门限

这是 pilot 建议门限，不是论文最终标准：

| 指标 | 建议门限 | 不通过时优先做什么 |
|---|---:|---|
| selected precision | ≥ 0.85 | 检查误报、目标选择器 |
| wrong target rate | ≤ 0.10 | 检查选择器/跟踪 |
| head_missed rate | ≤ 0.30 | 确认 head 可见性；必要时定向补 head 数据 |
| track_break rate | ≤ 0.30 | 优先修 tracker，而不是扩数据 |
| same-target continuity | ≥ 0.60 | 修 tracker/目标关联 |
| usable episode rate（≥5 帧） | ≥ 0.50 | 修 tracker 或重录 |

任一指标不通过时：

- 不要训练分类器；
- 不要用当前数据做 H/B 行为结论；
- 先修 tracker 或做定向采集。

---

## 8. 决策矩阵

| QC 结果 | 结论 | 下一步 |
|---|---|---|
| 目标覆盖好、track 稳定 | 数据可用于描述统计 | 每类补到 ≥3 sessions |
| 目标覆盖好、track 碎片 | tracker 是主瓶颈 | 先修目标关联/重捕获 |
| 目标覆盖差、误报多 | 检测/场景有问题 | 定向采集或调整采集场景 |
| head 明确可见但长期漏检 | head 数据/模型是瓶颈 | 再考虑定向 head 数据；不直接重训 |
| 目标大部分不可见 | 采集场景无效 | 重录，不扩现有数据 |

---

## 9. 输出

包含：

```text
P0C_QC_TEMPLATE.csv 的填写副本
QC 汇总 JSON/CSV
分歧记录
最终 QC 结论（通过/不通过/需修 tracker）
```

建议保存到：

```text
runs/eval/anticheat_p0c/pilot_old_tiled_v1/qc/manual/
```

不要覆盖 contact sheets 或源 session。

---

## 10. 明确禁止

- 不用普通桌面视频冒充 CS2 POV；
- 不用 proxy/合成轨迹补充 QC；
- 不把单帧 `UNCERTAIN` 强行判成作弊；
- 不在 QC 未通过时训练分类器；
- 不修改源视频、模型权重和已有 session；
- 不把 `check_fps_pilot` 的文件哈希通过当成人工 QC 通过。