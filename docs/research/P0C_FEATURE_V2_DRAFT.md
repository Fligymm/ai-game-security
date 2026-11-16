# P0-C Feature v2 草案与实现边界

日期：2026-11-16  
状态：**设计草案；未实现、未训练分类器**

目标：用现有 5H/5B 的 old-model tiled 输出，设计一组有行为含义、可消融、
可跨 session 检查的视觉行为特征，先判断是否存在稳定信号，再决定是否扩数据。

---

## 1. 为什么需要 v2

当前 v1 特征主要是：

```text
detection_frame_ratio
selected_frame_ratio
mean_detections_per_frame
selected_head_ratio
unique_selected_tracks
track_switches_per_frame
acquisition_episodes_per_frame
selected_episode_duration_mean/max
mean/median/p95 offset
mean_selected_confidence
```

问题：

- 很多是 session 级汇总，容易编码场景/操作者/录制条件；
- offset 直接取绝对值，受目标距离/视角影响；
- 没有区分“目标可见但未选中”和“目标不可见”；
- 没有区分 acquisition、tracking、correction、switching；
- 5H/5B baseline 仅 6/10，AUC 0.68/0.72，说明需要更有结构的特征。

---

## 2. 单位与分析边界

### 2.1 单位

```text
输入：inference_frames.jsonl（逐帧）
中间单位：episode（目标可见/选中连续片段）
输出：session-level 特征
```

### 2.2 不使用的字段

不要直接作为分类特征：

```text
frames / capture_duration
绝对 frame_index
绝对 capture_time
session_id / operator_id
unique_selected_tracks（原始计数）
raw head/body counts（原始计数）
```

这些容易成为 session/场景指纹。可以用**每秒速率、比例、分位数**替代。

### 2.3 泄漏控制

- 按 session 做 train/test；
- 归一化/分位数只在训练折拟合；
- 不用帧级随机切分；
- 不使用同一录像的窗口跨集合；
- 先做 leave-one-session-out；足够数据后再 leave-one-operator/scene-out。

---

## 3. Episode 定义

### 3.1 可见 episode

从 `detections` 中选一个目标类（head 或 body），按时间连续检测：

- 相邻检测帧间隔 ≤ 0.15 s 视为同一可见 episode；
- 超过 0.15 s 断开；
- 如果目标类别（head/body）发生变化，分成不同 episode；
- 不依赖 track ID，避免 ID 碎片直接破坏 episode。

### 3.2 选中 episode

从 `selected` 非空帧连续片段：

- 相邻选中帧间隔 ≤ 0.15 s 视为同一段；
- track ID 变化不强行切断，但单独记录；
- 同时记录对应可见 episode。

### 3.3 对齐

每个选中 episode 对齐到包含它的可见 episode：

```text
visible_start
visible_end
selected_start
selected_end
```

---

## 4. Feature v2 家族

### F1 目标获取（Acquisition）

| 特征 | 定义 |
|---|---|
| `acq_delay_s` | selected_start - visible_start |
| `acq_delay_ratio` | acq_delay / visible_duration |
| `pre_select_visible_frames` | 可见但未选中的帧数 |
| `pre_select_visible_ratio` | 可见但未选中帧 / visible frames |
| `acq_delay_median_s` | episode 级中位数 |

含义：目标出现后多久才被选择；是否先观察再锁定。

### F2 跟踪稳定性（Tracking）

| 特征 | 定义 |
|---|---|
| `offset_mean_norm` | offset / 目标框对角线（或画面对角线） |
| `offset_median_norm` | 同上，中位数 |
| `offset_cv` | offset 的变异系数 |
| `offset_slope` | 选中片段内 offset 对时间的斜率 |
| `settling_time_s` | 从 selected_start 到 offset 首次低于中位数 50% 的时间 |
| `jitter_ratio` | 相邻帧 offset 差分的平均绝对值 / 平均 offset |

含义：选择后是否稳定收敛，还是持续抖动。

### F3 修正/过冲（Correction）

从 `compensated_offset` 的逐帧变化计算：

| 特征 | 定义 |
|---|---|
| `sign_flip_rate` | dx/dy 符号翻转次数 / selected frames |
| `correction_magnitude_mean` | 修正向量幅度均值 |
| `overshoot_proxy_rate` | offset 先下降后上升的 episode 比例 |
| `path_efficiency` | 首末位移 / 路径长度 |
| `trajectory_straightness` | 使用现有 `features.straightness` 的 episode 均值 |

含义：人类修正/过冲模式与合成/规则行为可能不同，但不能预设方向。

### F4 目标切换/重捕获（Switching）

| 特征 | 定义 |
|---|---|
| `switch_rate_per_visible_s` | track/目标中心跳变次数 / 可见时长 |
| `head_body_switch_rate` | head/body 选中切换次数 / selected frames |
| `reacquire_gap_mean_s` | 断开后重新选中的平均间隔 |
| `post_switch_settle_s` | 切换后 offset 回到中位数 50% 的时间 |
| `switch_with_overlap_ratio` | 切换前后框 IoU≥0.3 的比例（ID churn 代理） |

含义：区分“目标切换”与“检测抖动”；避免把 ID 碎片当行为。

### F5 可见性/上下文（Visibility）

| 特征 | 定义 |
|---|---|
| `visible_duration_median_s` | 可见 episode 时长中位数 |
| `visible_fraction` | 有目标检测的帧 / 总帧 |
| `selected_fraction_of_visible` | selected frames / visible frames |
| `target_area_median_norm` | 目标框面积 / 画面面积 |
| `target_confidence_mean` | 选中目标置信度均值 |
| `occlusion_gap_mean_s` | 检测断开的平均时长（遮挡/丢失代理） |

含义：控制“目标是否容易看见”，防止把可见性差异误判为行为差异。

### F6 归一化/聚合

- 所有时间特征用秒；
- 所有计数用每秒/每可见秒归一化；
- offset 使用归一化（框对角线/画面对角线）；
- session 内 z-score 仅作为可选实验，不默认；
- 对每个特征报告 median 和 IQR，不只 mean。

---

## 5. 需要的实现

新增：

```text
tools/extract_p0c_features_v2.py
```

输入：

```text
runs/eval/anticheat_cv_offline/<session>_v0_tiled/inference_frames.jsonl
```

输出：

```text
runs/eval/anticheat_p0c/features_v2/
├── frames_v2.csv          # 逐帧中间量（可选，受控大小）
├── episodes_v2.csv        # visible/selected episode 对齐
├── features_v2.csv        # session-level 特征
└── features_v2_meta.json  # 来源、模型/视频 SHA、版本
```

实现边界：

- 只读取 existing old-model tiled outputs；
- 不重跑检测/跟踪；
- 不修改 `AimPipeline`、`ByteTrack`、模型；
- 不训练分类器；
- 不扩数据；
- 不改 capture/session 格式。

测试：

- episode 切分边界（gap、类别切换）；
- acquisition delay 计算；
- offset 归一化；
- leave-one-session-out 的 fold 无泄漏；
- 缺失字段/空 episode 的降级。

---

## 6. 评估协议

### 6.1 首轮：现有 5H/5B

- 只做 leave-one-session-out；
- 模型：Dummy、LogisticRegression、RandomForest；
- 指标：accuracy、balanced accuracy、ROC-AUC、PR-AUC、TPR@FPR=1%、confusion；
- 与 v1 baseline 对比；
- 特征家族 ablation：
  - F1 only
  - F2 only
  - F1+F2
  - F1+F2+F3+F4+F5
- 错误分析：哪些 session 被错分，是否集中在某个操作者/场景。

### 6.2 Go/no-go

建议门槛：

```text
v2 的 LOO AUC >= 0.75
且错误不集中在单一 session
且至少两个特征家族有独立贡献
```

不满足：

- **不扩数据**；
- 重新审视特征/问题设定；
- 不通过调参追指标。

满足：

- 再扩到 10H/10B + 多场景；
- 做 leave-one-session/operator/scene-out；
- 再决定论文形式。

---

## 7. 论文定位

如果 v2 有稳定信号，论文主线应是：

> 屏幕视觉可观察的瞄准行为特征基准：跨 session 的 H/B 差异与鲁棒性分析。

而不是：

> 一个 99% 准确的作弊检测器。

如果 v2 仍无信号，负结果本身可以作为：

- 小样本 proxy 数据高估性能的证据；
- 视觉行为特征局限性的分析；
- 但需要更强的实验设计和更多 session 才可发表。

---

## 8. 当前决定

```text
先实现 Feature v2（草案阶段）
只跑 5H/5B
不训练正式分类器
不扩数据
不启用 new 模型
```

实现完成后再做一次 go/no-go，决定是否进入 10H/10B 扩样。