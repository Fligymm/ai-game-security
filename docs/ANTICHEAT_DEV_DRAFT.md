# 反作弊行为检测开发草案

版本：v0.2.1  
日期：2026-11-15  
状态：**P0-A approved; P0-B not started**  
修订依据：[`docs/research/ACADEMIC_FEASIBILITY_REVIEW.md`](research/ACADEMIC_FEASIBILITY_REVIEW.md)

> 关联主线：[`PROJECT_ROADMAP.md`](PROJECT_ROADMAP.md)  
> 前置边界：继续遵守 [`ACADEMIC_USE_NOTICE.md`](ACADEMIC_USE_NOTICE.md) 和
> [`LEGAL_AND_ETHICS.md`](LEGAL_AND_ETHICS.md)；不接正式服务器，不发布可运行作弊工具。

---

## 0. 修订说明

v0.1 把当前阶段描述为“没有检测模型”，这不准确。实际存在的资产包括：

```text
models/baseline_detector.joblib       已保存的 RandomForest/IsolationForest baseline
datasets/evaluation_report.json       OOF ROC-AUC 0.9996 / PR-AUC 0.9987
tools/train_baseline_detector.py      训练与报告代码
```

更准确的表述是：

> **已有一个 proxy 行为分类 baseline，但它没有被验证为 FPS 反作弊检测。**

v0.2 的核心修改是：不再把“在现有 250 条轨迹上做一个更高 AUC”当作 MVP，而是把
**真实 FPS 行为数据、视觉-行为对齐、独立评测协议**列为 P0。现有 proxy 结果只保留
为预实验和负结果对照，不作为论文的核心证据。

---

## 1. 背景与结论

当前项目已经完成目标检测主线：

```text
model          cs2_multitarget_ft_v1
status         accepted final / frozen
external test  90 frames
mAP50          0.919
head mAP50     0.922
head R@0.35    0.780
empty FP       0/6
```

这部分可以作为 CV/工程能力的可靠证据，但它**不是反作弊准确率**。

反作弊行为方向目前的状态是：

| 能力 | 状态 |
|---|---|
| 行为轨迹 schema | 已有，`cv_agent/analytics/trajectory_schema.py` |
| 运动学/频谱特征 | 已有，`cv_agent/analytics/features.py` |
| Proxy baseline | 已有，`models/baseline_detector.joblib` |
| 真实 FPS 人体瞄准数据 | **没有** |
| 真实游戏内置 Bot 数据 | **没有** |
| CV Agent 与真实作弊的区分 | **没有** |
| 视觉帧与行为轨迹对齐 | **没有** |
| 独立行为测试集 | **没有** |
| 采样率/生成器 shortcut 审计 | **没有** |
| 误报率/校准/置信区间 | **没有** |

**结论：**

> 项目是一个“已完成目标检测、已有 proxy 行为 baseline、尚未完成 FPS 反作弊验证”的
> 应用型研究项目。下一阶段的关键不是换模型，而是换数据语义和实验协议。

---

## 2. 目标与非目标

### 2.1 研究目标

建立一个**仅依赖外部视觉/输入轨迹、可复现的 FPS 瞄准行为基准**，回答：

1. 正常人类、游戏内置 Bot、CV Agent 在目标获取、修正、过冲、切换和时序上是否存在
   可测差异？
2. 这些差异在跨 session、跨场景/地图、跨录制质量下是否稳定？
3. 仅依赖屏幕视觉信息（不读内存、不注入、不 Hook）能支持到什么程度的判断？
4. 视觉目标轨迹与输入行为轨迹结合，是否比单一模态更可靠？

### 2.2 当前阶段不做

- 不接线上游戏、不使用真实账号、不做真实对局测试。
- 不把 CV Agent 等同于真实外挂使用者。
- 不声称检测“所有作弊”或“真实作弊准确率”。
- 不发布可运行作弊工具、规避脚本、权重或原始轨迹。
- 不做自动封禁、驱动级检测、DMA/Kmbox 或反作弊绕过。
- 不重训已冻结的 `cs2_multitarget_ft_v1`。
- 不修改 `cv_agent.control`、`run_real.py`、kill switch 或已发布白名单。
- 不先上大规模 LSTM/Transformer；数据和协议优先。

---

## 3. 现有资产与关键更正

### 3.1 可保留的资产

| 资产 | 用途 | 处理 |
|---|---|---|
| `cs2_multitarget_ft_v1` | 视觉目标检测 | 冻结，不重训 |
| 150 帧检测数据 + 90 帧外部测试 | 目标检测评估 | 保留 |
| 回放对比 8,863 帧 | 检测稳定性/误报分析 | 保留 |
| `trajectory_schema.py` | 行为数据契约 | 扩展，不破坏旧 JSON |
| `features.py` | 运动学/频谱特征 | 复用并版本化 |
| `models/baseline_detector.joblib` | proxy baseline | 保留为预实验对照 |
| `datasets/evaluation_report.json` | proxy OOF 结果 | 只作负结果/对照，不作核心结论 |
| 测试与发布流程 | 可复现与合规 | 保留 |

### 3.2 必须纠正的认知

| 旧说法 | 更正 |
|---|---|
| “没有检测模型” | 已有 RandomForest/IsolationForest baseline |
| “human 是 FPS 玩家” | `capture_human.py` 是 tkinter 2D 点击任务 |
| “bot_agent 是游戏 Bot” | 是直线匀速生成器 |
| “synthetic 是 CV Agent” | 是人工合成轨迹生成器 |
| “0.9996 AUC 是反作弊准确率” | 是 proxy/generator 分离结果 |
| “行为数据可以支撑视觉行为结论” | 当前行为数据与 CS2 帧没有对齐 |

---

## 4. 核心科学问题与威胁模型

### 4.1 标签定义

论文中必须区分以下对象，不能混为一个“cheater”类：

```text
H  human           真实玩家，在受控离线 FPS 场景中完成瞄准任务
B  game_bot        游戏内置 Bot/离线 Bot，行为由游戏 AI 产生
C  cv_agent        仅基于屏幕视觉和输入模拟的受控 Agent
X  real_cheat      真实辅助瞄准使用者/真实外挂样本（当前没有）
```

当前数据只有：

```text
human        -> 2D 点击任务，不是 FPS
bot_agent    -> 几何直线生成器
synthetic    -> 合成生成器
```

因此当前最多支持：

> “2D pointing vs synthetic generator”的 proxy 研究。

不支持：

> “FPS 人类 vs 真实游戏 Bot vs 真实作弊者”的反作弊结论。

### 4.2 威胁模型

本阶段只研究**外部视觉可观察行为**：

- 输入：屏幕帧、检测框、跟踪轨迹、时间戳、可选输入轨迹；
- 不读取游戏内存、不注入、不 Hook、不修改游戏数据；
- 目标是估计行为异常/风险，不是证明意图；
- 任何输出都必须带“证据不足/需人工复核”的语义。

### 4.3 研究问题

- RQ1：真实 FPS 人类与游戏 Bot 的目标获取/修正/切换特征是否可区分？
- RQ2：CV Agent 与人类高手的行为差异在哪里？哪些差异是“机器痕迹”，哪些只是水平差异？
- RQ3：仅用视觉轨迹（检测+跟踪）能达到什么效果？加入输入轨迹后提升多少？
- RQ4：跨 session、跨地图、跨录制质量时，特征和分类器是否稳定？
- RQ5：拟人化（平滑、延迟、抖动）后，检测退化多少？

---

## 5. 数据契约与标签

### 5.1 保留现有 schema

现有 session JSON 字段：

```json
{
  "metadata": {
    "session_id": "human_0001_12347403",
    "source": "human",
    "target_distance_px": 1063.75,
    "target_size_px": 28.0,
    "reaction_time_ms": 3580.26,
    "seed": null
  },
  "time_series": {
    "timestamps": [0.0, 1.1894, 1.1904],
    "x": [1433.0, 967.0, 966.0],
    "y": [1156.0, 543.0, 542.0],
    "dx": [0, -466, -1],
    "dy": [0, -613, -1]
  },
  "events": [
    {"phase": "reaction_phase", "start_idx": 0, "end_idx": 1},
    {"phase": "coarse_move", "start_idx": 1, "end_idx": 601}
  ]
}
```

### 5.2 P0 需要新增的字段

为支持 FPS 和视觉对齐，新增（不破坏旧 JSON）：

```text
metadata:
  game, map, scene, weapon, sensitivity, fov
  resolution, recording_fps, capture_method
  agent_type: human | game_bot | cv_agent | real_cheat
  session_group: player/bot/agent id
  source_video_id, frame_time_base
  label_confidence / label_source

time_series:
  optional camera angles / view direction
  optional screen-space target track ids

alignment:
  video_frame_ranges
  target_track_ids
  event_frame_indices
```

### 5.3 标签规则

```text
human        -> 0 (正常人类)
game_bot     -> 1 (游戏 AI)
cv_agent     -> 2 (受控视觉 Agent)
real_cheat   -> 3 (仅在获得合规样本时)
```

禁止：

- 把 `cv_agent` 和 `real_cheat` 合并；
- 把 `synthetic_adversarial` 直接称为真实外挂；
- 只在混合标签上报告一个 AUC 就宣称“检测作弊”。

### 5.4 数据校验

- `timestamps/x/y/dx/dy` 等长且时间严格递增；
- `dx/dy` 与位置差分一致（允许 ±1 px）；
- `events` 范围合法且不重叠；
- 每条 session 必须能追溯到视频/采集记录；
- 训练/测试按 `session_group` 和 `map/scene` 分组；
- 禁止同一玩家/同一录像的窗口跨集合。

---

## 6. 为什么当前数据不能支撑 FPS 结论

这不是“数据少一点”的问题，而是语义不匹配：

| 维度 | 当前 human | FPS 需要 |
|---|---|---|
| 任务 | tkinter 点击圆点 | 3D 视角瞄准 |
| 输入 | 2D 画布鼠标移动 | 鼠标 look + 移动/射击 |
| 目标 | 固定屏幕上的圆 | 游戏内 3D 目标 |
| 场景 | 单一 UI | 地图/距离/遮挡/武器 |
| 反馈 | 点击是否命中 | 命中、后坐力、移动、peek |
| 对手 | 无 | Bot/玩家/CV Agent |

此外，时序分布本身已经暴露生成器差异：

```text
human:     601 points, median dt ≈ 0.00103 s, initial gap ≈ 1.189 s
bot:        31 points, median dt ≈ 0.00827 s, reaction time 0
synthetic: 130 points, median dt ≈ 0.00833 s, reaction time ≈ 0.185 s
```

因此现有 0.9996 OOF AUC 必须标注为：

> **proxy generator-separation result, not anti-cheat accuracy.**

---

## 7. 技术路线

### P0-A：威胁模型与标签（第 1 周）— **APPROVED**

状态：**2026-11-15 已批准并完成协议**  
产出：[`ANTICHEAT_LABEL_PROTOCOL.md`](ANTICHEAT_LABEL_PROTOCOL.md)

已完成：

- H/B/C/X 四类标签与旧 proxy 映射；
- 采集边界、纳入/排除条件、隐私边界；
- `agent_type` / `is_proxy` / `label_source` 字段；
- session + map/scene 分组切分与泄漏控制；
- 可声明/不可声明结论；
- P0-B pilot 的下一步门槛。

明确：**CV Agent ≠ 真实作弊；没有 X 数据时论文必须写“X not evaluated”。**

### P0-B：真实 FPS 行为采集（第 2–5 周）

状态：**窗口采集/生命周期/校验/CV 离线 dry-run 已实现；实际 H/B 采集仍 blocked（当前无 CS2/人类参与者）**  
Pilot 说明：[`ANTICHEAT_P0B_PILOT.md`](ANTICHEAT_P0B_PILOT.md)  
Agent 入口核查：[`ANTICHEAT_P0B_AGENT_READINESS.md`](ANTICHEAT_P0B_AGENT_READINESS.md)

最小采集矩阵：

```text
human:      ≥20 sessions, ≥3 maps/scenes, ≥2 weapons, ≥2 sensitivities
game_bot:   ≥20 sessions, same maps/scenes
cv_agent:   ≥20 sessions, same maps/scenes
real_cheat: 仅在合法、授权、隔离条件下；没有则不采集、不声称
```

Pilot 工具（R2 升级）：

```text
vision/stream/window_capture.py   指定 CS2 窗口 + fail-closed
tools/capture_fps_pilot.py        H/B 第一人称 POV + 生命周期
tools/check_fps_pilot.py          视频/哈希/窗口/POV/实验独立状态
tools/run_cv_agent_offline.py     C 离线 dry-run 与源视频关联
docs/ANTICHEAT_P0B_PILOT.md       H/B/C 新版流程
docs/ANTICHEAT_P0B_CAPTURE_REVIEW.md  R2-A 审查
```

要求：

- 独立 session，不用同一录像切帧伪造多个 session；
- 记录分辨率、FPS、灵敏度、FOV、地图、武器、录制方式；
- 同步屏幕帧与输入时间戳；
- 保留原始 session 和不可变 manifest；
- 先做 2–3 个 session 的 pilot，验证同步和标注，再扩大。

### P0-C：视觉-行为对齐（第 3–6 周）

- 用冻结检测器 + 跟踪器提取目标轨迹；
- 将目标 ID、框、时间戳与输入轨迹对齐；
- 生成目标获取、目标切换、跟踪误差、过冲/修正等事件；
- 记录检测误差和跟踪 ID switch，避免把检测错误当成行为异常；
- 产出联合 manifest：`video_id / frame_range / track_id / input_session_id`。

### P0-D：独立评测协议（第 6–8 周）

- 按 `session_group` + `map/scene` 分组；
- 固定 train/val/test；测试集只使用一次；
- 统一重采样到 60/120 Hz；
- 保留 raw/resampled 两套视图；
- 禁止窗口随机切分；
- 生成 `split_manifest.json` 和 `data_card.md`。

### P0-E：baseline、消融与指标（第 7–10 周）

baseline：

1. DummyClassifier；
2. LogisticRegression；
3. RandomForest/XGBoost；
4. 可选：序列模型（仅在特征 baseline 不足时）。

必须报告：

```text
ROC-AUC, PR-AUC
TPR @ FPR=1%, FPR @ TPR=95%
Brier/ECE
bootstrap 95% CI
per-class / per-map / per-scene
检测延迟（秒/窗口数）
```

### P1：鲁棒性与拟人化（第 10–13 周）

- 画质扰动：压缩、缩放、模糊、帧率变化；
- 拟人化扰动：平滑、随机延迟、抖动、限制角速度；
- 跨地图/场景验证；
- 特征消融：运动学 vs 频谱 vs 视觉事件 vs 输入轨迹；
- 误差分析：检测失败、跟踪 ID switch、标签噪声。

### P2：可选增强

- 视觉/行为 late fusion；
- 序列模型；
- 分析员复核/影子模式；
- 跨游戏泛化。

P2 不阻塞首篇论文。

---

## 8. 实验矩阵

| ID | 实验 | 目的 | 优先级 |
|---|---|---|---|
| E0 | 数据来源/标签审计 | 防止 proxy 混入核心结论 | P0 |
| E1 | raw vs resampled | 检测采样率/生成器 shortcut | P0 |
| E2 | session/map-held-out vs random split | 检测泄漏与泛化 | P0 |
| E3 | human vs game_bot | 真实对象可分性 | P0 |
| E4 | human vs cv_agent | 受控 Agent 差异 | P0 |
| E5 | visual-only vs input-only vs fusion | 视觉/行为增益 | P1 |
| E6 | 画质/帧率扰动 | 录制鲁棒性 | P1 |
| E7 | 拟人化扰动 | 规避鲁棒性 | P1 |
| E8 | 跨地图/跨 session | 泛化 | P1 |
| E9 | 序列模型对比 | 是否值得用深度时序 | P2 |

现有 250 条 proxy 轨迹只能用于：

- 数据审计工具开发；
- 特征/指标代码测试；
- 负结果对照（“proxy 数据会高估性能”）。

不能用于 E3/E4 的最终结论。

---

## 9. 指标与验收

### 9.1 P0 验收

- [ ] 真实 FPS 数据至少覆盖 3 个场景/地图，H/B/C 各 ≥20 sessions；
- [ ] 每个 session 有独立采集记录和 manifest；
- [ ] 视觉帧与输入轨迹可对齐，抽样人工核验通过；
- [ ] train/val/test 按 session + map/scene 分组，测试集未参与调参；
- [ ] 明确 H/B/C/X 标签，不把 C 当作 X；
- [ ] 重采样消融完成，证明指标不是采样率伪影；
- [ ] baseline（Dummy/Logistic/RF）与至少 2 组特征消融完成；
- [ ] 报告 PR-AUC、TPR@FPR=1%、FPR@TPR=95%、CI、ECE；
- [ ] 结果可复现；报告明确单游戏/小样本限制。

### 9.2 不使用“AUC > 0.9”作为验收

现有 proxy 数据的 0.9996 AUC 不能作为目标。P0 的验收重点是：

> **数据语义正确、视觉-行为对齐、无泄漏、可解释、可复现。**

如果真实数据上的 AUC 明显低于 proxy，这是正常且有价值的发现，不应为了追求数字
回头使用 proxy 数据。

---

## 10. 目录与模块建议

```text
anticheat/
  benchmark/
    __init__.py
    schema.py          # 扩展后的 session schema + 校验
    loader.py          # 读取/重采样/对齐
    split.py           # session + map/scene grouped split
  features/
    __init__.py
    kinematic.py       # 运动学特征
    visual_events.py   # 目标获取/切换/跟踪特征
  models/
    __init__.py
    baseline.py        # Dummy/Logistic/RF
  evaluation/
    __init__.py
    metrics.py         # ROC/PR/FPR/ECE/CI
  statistical/         # 保留现有 heuristic
```

工具：

```text
tools/capture_fps_behavior.py
tools/align_visual_behavior.py
tools/run_anticheat_benchmark.py
```

测试：

```text
tests/test_anticheat_schema.py
tests/test_anticheat_split.py
tests/test_anticheat_metrics.py
tests/test_anticheat_alignment.py
```

不修改：

```text
vision/*
cv_agent/control/*
run_real.py
已冻结的模型与权重
已发布的白名单
```

---

## 11. 计划与工作量

| 阶段 | 周 | 内容 | 交付 |
|---|---|---|---|
| P0-A | 1 | 标签/威胁模型 | 标签协议 |
| P0-B | 2–5 | 真实 FPS 采集 | 独立 sessions + manifest |
| P0-C | 3–6 | 视觉-行为对齐 | 联合 manifest + 事件特征 |
| P0-D | 6–8 | 独立评测协议 | split/data card |
| P0-E | 7–10 | baseline/消融/指标 | 报告 + 代码 + 测试 |
| P1 | 10–13 | 鲁棒性/拟人化/写作 | 论文初稿 |

总工作量估计 **9–13 周**。当前冻结检测模型和 90 帧测试不重做。

---

## 12. 风险与边界

| 风险 | 影响 | 缓解 |
|---|---|---|
| 用 proxy 数据冒充 FPS | 结论无效 | P0-B 强制真实采集 |
| CV Agent 被当作真实外挂 | 伦理/审稿风险 | H/B/C/X 分开标注 |
| 采样率/生成器 shortcut | AUC 虚高 | 重采样 + E1 消融 |
| 视觉/行为未对齐 | 不能声称视觉行为 | P0-C 联合 manifest |
| 窗口/录像泄漏 | 指标虚高 | session + map/scene 分组 |
| 样本小 | CI 宽 | 多 session、bootstrap CI |
| 拟人化规避 | 检测脆弱 | P1 扰动实验 |
| 伦理/法律 | 误用 | 离线、无真实控制、白名单 |

---

## 13. 评审时需要确认的问题

1. 是否同意把当前 proxy baseline 只作为预实验，不作为论文核心证据？
2. 是否批准 P0-B 的真实 FPS 行为采集（离线、受控、无真实账号）？
3. 是否接受 H/B/C/X 分开标注，并明确“CV Agent ≠ 真实作弊”？
4. 是否同意先做视觉-行为对齐，而不是先换 LSTM/Transformer？
5. 是否同意 P0 完成前不投稿、不宣称反作弊准确率？

默认建议：**五个问题都按“是”推进**；先做 P0-A 到 P0-E。

---

## 14. 阶段产出与简历写法

### P0 完成后

> 构建真实 FPS 人类/游戏 Bot/CV Agent 的独立 session 数据集，完成视觉目标轨迹与
> 输入轨迹对齐，按 session+map 分组建立 held-out benchmark；报告 PR-AUC、
> TPR@FPR=1%、校准和跨场景结果，并完成采样率 shortcut 消融。

### P1 完成后

> 评估画质、帧率、地图变化和拟人化扰动下的检测鲁棒性，给出视觉/行为特征消融和
> 误差分析。

### 不可写成

```text
“反作弊准确率 99.96%”
“检测真实外挂”
“生产级反作弊系统”
```

---

## 15. 决策记录

| ID | 日期 | 状态 | 内容 |
|---|---|---|---|
| AC-D001 | 2026-11-15 | Draft | 反作弊作为下游研究支线 |
| AC-D002 | 2026-11-15 | Draft | 不重训冻结视觉模型，不接线上 |
| AC-D003 | 2026-11-15 | **Superseded** | v0.1 的“用现有 250 条轨迹做 MVP”被 v0.2 替代 |
| AC-D004 | 2026-11-15 | Draft | 现有 0.9996 AUC 仅作 proxy 对照，不作反作弊结论 |
| AC-D005 | 2026-11-15 | Draft | P0 必须包含真实 FPS 数据和视觉-行为对齐 |
| AC-D006 | 2026-11-15 | Draft | H/B/C/X 分开标注，CV Agent 不等于真实作弊 |
| AC-D007 | 2026-11-15 | **Approved** | P0-A 标签/威胁模型协议批准；进入 P0-B pilot，尚未采集数据 |
| AC-D008 | 2026-11-15 | **Tooling ready / data blocked** | P0-B 窗口采集、生命周期、校验与 C 离线 dry-run 工具完成；当前无 CS2/人类参与者，未伪造数据 |

本草案通过评审后，再更新 `docs/PROJECT_ROADMAP.md` 的范围和状态看板，并同步
[`docs/research/ACADEMIC_FEASIBILITY_REVIEW.md`](research/ACADEMIC_FEASIBILITY_REVIEW.md)
的结论。