# 论文方向建议

日期：2026-11-17  
状态：**方向建议；不新增数据、不训练分类器**

---

## 1. 结论先行

综合当前模型、数据集和后续可支持性，最合适的论文方向不是：

```text
“高准确率 H/B 作弊检测器”
```

而是：

> **屏幕视觉瞄准行为分析的可复现基准与混杂因素研究：以 H/B 小样本为例**

英文可写：

> *Screen-Only Aim Behavior Analysis: A Reproducible H/B Pilot Benchmark and the Limits of Visual Tracking Error*

这是一篇 **benchmark / measurement / negative-result** 方向的论文，而不是检测器论文。

---

## 2. 为什么不选分类器论文

当前证据：

```text
固定 F2，21 sessions: AUC 0.918
但混入地图 confound

平衡 10H/10B: RF 0.85 / AUC 0.90
nuke 单独仅 0.60 / AUC 0.68

F2 residualized: AUC 0.55
不变特征 residualized: AUC 0.57
目标面积/可见性匹配: acc 0.60，AUC 0.75–0.76
```

结论：

- F2 的判别力主要来自目标可见性/目标大小；
- 地图平衡后仍不稳定；
- 没有可靠的行为分类信号；
- 继续调参或扩同条件数据只会过拟合。

因此“分类器论文”在审稿中会被直接质疑：

```text
你的模型是不是在分类地图/目标距离/可见性？
```

---

## 3. 推荐论文主线

### 题目方向

```text
屏幕视觉瞄准行为的可复现基准与视觉跟踪误差的局限
——以 Human / Game Bot 小样本为例
```

### 核心贡献

1. **可复现的 first-person H/B 采集协议**
   - fail-closed 窗口捕获；
   - POV/实验 attestation；
   - timebase/hash 校验；
   - session 级元数据和 QC。

2. **检测模型的域/尺度审计**
   - 旧模型 vs 微调模型；
   - 320×320 ROI 微调在 1920×1080 POV tiled 场景下 head 塌缩；
   - 说明“ROI 指标提升”不等于“POV 可用”。

3. **P0-C 行为特征基准**
   - F1 acquisition；
   - F2 tracking；
   - F3 correction；
   - F4 switching；
   - F5 visibility；
   - 3H/3B、5H/5B、10H/10B 的逐级验证。

4. **Confound 分析（论文的核心负结果）**
   - 地图 confound：dust2/nuke/aim_botz；
   - 可见性/目标大小 confound；
   - F2 residualized 后接近 chance；
   - 匹配子集仍不稳定。

5. **可复现性/实验规范建议**
   - 地图必须人工确认；
   - H/B 必须在同一地图配对；
   - 目标大小/可见性需匹配；
   - 不应把 offset 大小直接解释为行为差异；
   - 负结果也应报告。

---

## 4. 论文结构草案

```text
1. Introduction
   screen-only anti-cheat 的问题；为什么 H/B 行为分析困难

2. Related Work
   game bot detection；aim behavior；visual behavior analysis；dataset confounds

3. P0-B Capture Protocol
   window capture；POV attestation；timebase/hash；QC

4. Detection Model Audit
   old vs fine-tuned；ROI/POV domain shift；head collapse

5. P0-C Feature Benchmark
   F1–F5；session-level features；LOO evaluation

6. Confound Analysis
   map；visibility；target size；residualization；matching

7. Negative Results and Lessons
   F2 不可作为行为结论；数据集设计建议

8. Threats to Validity
   小样本、单游戏、proxy labels、无真实外挂

9. Reproducibility
   scripts、session IDs、splits、checks

10. Conclusion
```

---

## 5. 目标venue建议

### 最合适

```text
applied ML / security workshop
game AI / games conference short paper
applied cybersecurity journal
```

例如方向：

- game security / anti-cheat workshop；
- IEEE Conference on Games 的 short paper；
- Computers & Security / Entertainment Computing 类应用期刊（需扩展）。

### 不适合

```text
顶级安全会议 full paper
顶级 CV 会议
以“检测率”为主张的论文
```

原因：

- 数据量小；
- 单游戏；
- 无真实外挂；
- 核心结果是负结果/测量问题，不是 SOTA 检测。

---

## 6. 备选方向

### 备选 A：检测模型域漂移短论文

主题：

> ROI fine-tuning causes POV head collapse in lightweight game-screen detectors

优点：

- 现有 90 帧 ROI 测试 + POV 5H/5B 数据；
- old/new 对比明确；
- 不需要行为分类。

缺点：

- 只有一个检测模型族；
- 检测数据集只有 119/30；
- 更适合 short paper/technical report。

### 备选 B：P0-B 数据集论文

不推荐作为主方向：

- 10H/10B 规模太小；
- 单游戏；
- 行为标签只有 session 级；
- 不足以支撑 dataset track。

---

## 7. 后续可支持性评估

| 方向 | 数据是否够 | 模型是否够 | 风险 | 推荐度 |
|---|---|---|---|---|
| Benchmark/negative result | 够 | 够 | 中 | ★★★★★ |
| 检测模型域漂移 short paper | 基本够 | 够 | 中 | ★★★★ |
| P0-B dataset paper | 不够 | 不适用 | 高 | ★★ |
| H/B 分类器论文 | 不够 | 不够 | 极高 | ★ |

当前无需新增数据；现有 10H/10B + 6H cross-map + old/new model 足够支撑
benchmark/negative-result 主线。

---

## 8. 建议的下一步

1. 冻结数据：
   - dust2 5H/5B；
   - nuke 5H/5B；
   - aim_botz 6H 作为 cross-map；
2. 冻结分析：
   - 不再改 F2；
   - 不再扩同条件数据；
3. 写论文提纲和贡献列表；
4. 先投 workshop/short paper；
5. 若审稿要求扩展，再考虑：
   - 控制目标距离/可见性的新采集；
   - 第三个地图的 H/B 配对；
   - 新特征族。

---

## 9. 工作草稿

短论文工作草稿：

- [`SHORT_PAPER_DRAFT.md`](SHORT_PAPER_DRAFT.md)

当前草稿已包含：协议、模型审计、F2 结果、confound 分析、限制和负结果。
引用、图表和 venue 模板仍待补。

## 10. 一句话

**最合适的论文方向是“可复现基准 + 混杂因素 + 负结果”的测量型论文，
而不是继续抢救一个被 confound 主导的 H/B 分类器。**