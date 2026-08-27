
# AI Game Security Lab

> 基于计算机视觉、行为建模与对抗学习的游戏 AI Anti-Cheat 实验与研究平台

## 1. 项目定位

本项目用于研究以下问题：

- 如何使用 YOLO 等计算机视觉模型理解 FPS 游戏画面
- 如何在离线、可控的游戏环境中模拟视觉辅助行为
- 如何采集 Human / Game Bot / CV-based Agent 的行为数据
- 如何通过行为时序特征识别异常辅助行为
- 如何构建传统机器学习、序列模型和 Transformer Anti-Cheat
- 如何研究检测模型与视觉辅助 Agent 之间的对抗关系
- 如何评估 Anti-Cheat 模型的鲁棒性与跨游戏泛化能力

### 核心研究闭环

```text
Attack / Simulation
        ↓
Behavior Observation
        ↓
Data Collection
        ↓
Feature Engineering
        ↓
Detection
        ↓
Adversarial Evasion
        ↓
Robust Detection
        ↓
Cross-Game Evaluation
```

### 实验边界

项目优先使用：

- CS2 Workshop / 离线训练环境
- CS2 Demo / Replay
- 自己录制的合法游戏录像
- 开源离线 FPS
- 开源数据集
- 本地、隔离的实验环境

避免针对真实联网竞技服务实施作弊、绕过商业反作弊或影响其他玩家。

---

# 2. 总体架构

```text
AI Game Security Lab
│
├── 01. 实验环境层
│   ├── CS2 Offline / Workshop
│   ├── CS2 Demo / Replay
│   ├── 开源 FPS
│   └── Game Video
│
├── 02. 数据采集层
│   ├── Game Frame
│   ├── Game State
│   ├── Input
│   ├── Camera
│   ├── Target
│   ├── Shooting
│   └── Hit / Kill
│
├── 03. Computer Vision
│   ├── Preprocessing
│   ├── YOLO Detection
│   ├── Player Detection
│   ├── Head Detection
│   ├── Multi-object Tracking
│   ├── Target State
│   └── CV Benchmark
│
├── 04. CV Agent Simulation
│   ├── Target Selection
│   ├── Target Prediction
│   ├── Aim Controller
│   ├── Trajectory Generation
│   └── Timing Model
│
├── 05. Behavior Analysis
│   ├── Mouse Trajectory
│   ├── Camera Trajectory
│   ├── Target Trajectory
│   ├── Reaction Time
│   ├── Aim Error
│   ├── Movement Statistics
│   └── Temporal Features
│
├── 06. Anti-Cheat
│   ├── Rule Based
│   ├── Statistical Detection
│   ├── Classical ML
│   ├── Sequence Model
│   ├── Transformer
│   └── Ensemble
│
├── 07. Adversarial Research
│   ├── Detection Evasion
│   ├── Randomization
│   ├── Smoothing
│   ├── Timing Variation
│   ├── Behavior Mimicry
│   └── Robust Detection
│
├── 08. Benchmark
│   ├── Detection
│   ├── Tracking
│   ├── Behavior Classification
│   ├── Anti-Cheat
│   ├── Robustness
│   └── Generalization
│
└── 09. Research Output
    ├── Dataset
    ├── Models
    ├── Experiments
    ├── Visualization
    ├── Reports
    └── Paper
```

---

# 3. 实验环境

## 3.1 CS2 Workshop

主要作为第一实验环境。

研究方向：

- 静态目标
- 移动目标
- Bot Peek
- Reaction Training
- Aim Training
- Target Switching
- 不同距离
- 不同目标数量
- 不同地图环境

目标：

> 建立一个可重复、可控制、接近真实 FPS 场景的视觉实验环境。

## 3.2 CS2 Demo / Replay

主要作为 Human Behavior 数据来源。

研究：

- 真实玩家瞄准
- 目标切换
- 视角变化
- 移动
- 射击
- 击杀
- 反应行为

## 3.3 开源 FPS

作为第二实验环境，用于验证模型泛化能力。

候选：

- AssaultCube
- Xonotic
- OpenArena
- 其他具有离线 Bot 的开源 FPS

## 3.4 游戏录像

用于纯视觉研究。

重点：

- Player Detection
- Tracking
- Trajectory
- Scene Understanding
- Cross-game Visual Generalization

---

# 4. 数据集体系

```text
datasets/
│
├── human/
│   ├── raw/
│   ├── frames/
│   ├── trajectories/
│   └── labels/
│
├── bot/
│   ├── raw/
│   ├── frames/
│   ├── trajectories/
│   └── labels/
│
├── cv_agent/
│   ├── raw/
│   ├── frames/
│   ├── trajectories/
│   └── labels/
│
└── adversarial/
    ├── raw/
    ├── trajectories/
    └── labels/
```

## 4.1 Human Dataset

来源：

- 自己录制
- CS2 Demo
- 合法公开 Demo / 数据集

包含：

- Mouse
- Camera
- Target
- Shooting
- Hit
- Kill
- Target Switching
- Reaction

## 4.2 Game Bot Dataset

来源：

- CS2 Offline Bot
- 开源 FPS Bot

用于：

> 区分“游戏 AI 行为”和“人类行为”。

## 4.3 CV Agent Dataset

用于模拟视觉辅助 Agent 的行为。

研究类别：

- Direct
- Smooth
- Predictive
- Delayed
- Human-like

## 4.4 Adversarial Dataset

用于研究：

- 行为扰动
- 时间扰动
- 轨迹扰动
- 分布变化
- 检测规避

---

# 5. Computer Vision

```text
Game Frame
    ↓
Preprocessing
    ↓
YOLO
    ↓
Object Detection
    ↓
Tracking
    ↓
Target State
    ↓
Trajectory
```

## 5.1 Detection

研究：

- Player Detection
- Head Detection
- Target Detection
- Detection Confidence
- Occlusion
- Small Target
- Fast Target

## 5.2 Tracking

研究：

- Multi-object Tracking
- Target ID
- Target Switching
- Track Stability
- Occlusion Recovery

## 5.3 Prediction

研究：

- Target Position
- Target Velocity
- Target Direction
- Short-term Trajectory
- Prediction Error

## 5.4 Benchmark

记录：

- Precision
- Recall
- mAP
- FPS
- Latency
- Localization Error
- Tracking Accuracy

---

# 6. CV Agent Simulation

> 本模块用于离线、隔离环境中的研究模拟。

```text
Vision
  ↓
Detection
  ↓
Target Selection
  ↓
Target Prediction
  ↓
Controller
  ↓
Trajectory Generator
  ↓
Virtual / Experimental Input
```

模块：

```text
cv_agent/
├── detection/
├── selection/
├── prediction/
├── control/
├── trajectory/
└── timing/
```

## 6.1 Target Selection

研究：

- 最近目标
- 视野内目标
- 优先级
- Target Switching

## 6.2 Target Prediction

研究：

- 静态预测
- 速度预测
- 方向预测
- 短期轨迹预测

## 6.3 Controller

研究：

- 直接控制
- 平滑控制
- 延迟控制
- 不同控制策略的轨迹差异

## 6.4 Trajectory

生成并分析：

- Aim Trajectory
- Camera Trajectory
- Target Tracking Trajectory

---

# 7. Behavior Analysis

这是项目的核心研究模块。

```text
Raw Behavior
      ↓
Feature Extraction
      ↓
Temporal Representation
      ↓
Behavior Embedding
      ↓
Classification
```

## 7.1 Mouse Features

研究：

- Position
- Delta
- Velocity
- Acceleration
- Jerk
- Direction
- Direction Change
- Movement Frequency

## 7.2 Camera Features

研究：

- Rotation
- Angular Velocity
- Angular Acceleration
- View Change
- Stabilization

## 7.3 Aim Features

研究：

- Aim Error
- Acquisition Time
- Correction
- Overshoot
- Stabilization
- Target Lock Duration

## 7.4 Target Features

研究：

- Position
- Velocity
- Direction
- Distance
- Visibility
- Target Switching

## 7.5 Temporal Features

研究：

- Reaction Time
- Target Acquisition Time
- Fire Timing
- Switching Time
- Continuous Behavior

---

# 8. Human vs Bot vs CV Agent

建立三类基准：

```text
Human
  ↓
正常玩家行为

Game Bot
  ↓
游戏内部 AI 行为

CV Agent
  ↓
视觉辅助 Agent 行为
```

重点比较：

```text
Human
 VS
Game Bot
 VS
CV Agent
```

分析：

- Aim Trajectory
- Reaction Time
- Target Switching
- Movement
- Correction
- Shooting Timing
- Temporal Pattern

---

# 9. Anti-Cheat

按照复杂度逐步建立。

```text
Level 1
Rule Based
      ↓
Level 2
Statistical Detection
      ↓
Level 3
Classical ML
      ↓
Level 4
MLP
      ↓
Level 5
LSTM / GRU
      ↓
Level 6
Transformer
      ↓
Level 7
Multi-modal Detection
```

## 9.1 Rule Based

研究：

- Threshold
- Heuristic
- FSM
- Simple Anomaly Detection

## 9.2 Statistical

研究：

- Distribution
- Outlier
- Probability
- Hypothesis Testing
- Population Difference

## 9.3 Classical ML

候选：

- Random Forest
- XGBoost
- SVM
- Logistic Regression

## 9.4 Sequence Model

候选：

- LSTM
- GRU
- Temporal CNN

## 9.5 Transformer

研究：

- Trajectory Transformer
- Temporal Attention
- Multi-feature Attention
- Long-range Behavior

## 9.6 Multi-modal

输入：

```text
Mouse
+
Camera
+
Target
+
Timing
+
Shooting
+
Trajectory
```

输出：

```text
Legitimate
Suspicious
Cheat
```

或：

```text
Cheat Probability
```

---

# 10. Adversarial Research

研究闭环：

```text
CV Agent
   ↓
Anti-Cheat
   ↓
Detection
   ↓
Behavior Evasion
   ↓
Anti-Cheat
   ↓
Robust Detection
```

## 10.1 Evasion Categories

研究：

- Smoothing
- Randomization
- Timing Variation
- Trajectory Variation
- Prediction Variation
- Behavioral Mimicry
- Distribution Shift

## 10.2 Defense

研究：

- Robust Features
- Adversarial Training
- Temporal Detection
- Multi-modal Detection
- Ensemble Detection
- Continual Learning

---

# 11. Anti-Cheat Evaluation

统一评估：

## Classification

- Accuracy
- Precision
- Recall
- F1
- ROC-AUC
- PR-AUC
- False Positive Rate
- False Negative Rate

## Detection

- Detection Rate
- Detection Latency
- Suspicion Score
- Early Detection Time

## Robustness

- Evasion Rate
- Robust Accuracy
- Performance Degradation
- Distribution Shift Performance

---

# 12. Cross-Game Generalization

训练环境：

```text
CS2
```

测试环境：

```text
Xonotic
AssaultCube
OpenArena
其他 FPS
```

研究：

```text
Game-specific Features
        VS
Game-agnostic Features
```

目标：

> 判断 Anti-Cheat 是否能够学习到跨游戏通用的异常行为特征。

---

# 13. Visualization

建立：

```text
visualization/
├── detection/
├── tracking/
├── trajectory/
├── behavior/
├── anticheat/
└── benchmark/
```

重点可视化：

```text
Human Aim
    VS
Game Bot Aim
    VS
CV Agent Aim
    VS
Human-like CV Agent Aim
```

以及：

- Target Trajectory
- Camera Trajectory
- Mouse Trajectory
- Aim Error
- Reaction Time
- Cheat Probability
- Detection Timeline
- Model Comparison

---

# 14. Benchmark Framework

```text
benchmarks/
│
├── vision/
│   ├── detection/
│   └── tracking/
│
├── behavior/
│   ├── feature/
│   └── classification/
│
├── anticheat/
│   ├── rule/
│   ├── ml/
│   └── transformer/
│
└── adversarial/
    ├── evasion/
    └── robustness/
```

每次实验应记录：

```text
Experiment ID
Environment
Dataset
Model
Configuration
Training Data
Test Data
Metrics
Results
Observations
Conclusion
```

---

# 15. 实验阶段规划

## Phase 0 — Environment

目标：

- 建立 CS2 Workshop 实验环境
- 建立 Demo / Replay 数据源
- 建立开源 FPS 第二环境
- 建立统一实验配置

## Phase 1 — Computer Vision

目标：

- 完成 FPS Player Detection
- 完成 Tracking
- 完成 Target State
- 完成 CV Benchmark

## Phase 2 — Behavior Dataset

目标：

- 建立 Human Dataset
- 建立 Game Bot Dataset
- 建立 CV Agent Dataset
- 建立统一数据格式

## Phase 3 — Behavior Analysis

目标：

- 建立轨迹分析
- 建立特征工程
- 分析 Human / Bot / CV Agent 差异

## Phase 4 — Anti-Cheat Baseline

目标：

```text
Rule
 ↓
Statistical
 ↓
Random Forest / XGBoost
```

建立第一个检测基线。

## Phase 5 — Deep Anti-Cheat

目标：

```text
LSTM
 ↓
GRU
 ↓
Transformer
```

比较不同时间序列模型。

## Phase 6 — Adversarial Research

目标：

```text
CV Agent
 ↓
Evasion
 ↓
Detection
```

研究模型鲁棒性。

## Phase 7 — Cross-Game

目标：

```text
Train: Game A
Test: Game B
```

研究跨游戏泛化。

## Phase 8 — Research Output

形成：

- Dataset
- Benchmark
- Models
- Visualization
- Experiment Reports
- Research Paper
- GitHub Repository

---

# 16. Repository Structure

```text
ai-game-security/
│
├── datasets/
│   ├── human/
│   ├── bot/
│   ├── cv_agent/
│   └── adversarial/
│
├── vision/
│   ├── detection/
│   ├── tracking/
│   ├── prediction/
│   └── benchmark/
│
├── cv_agent/
│   ├── detection/
│   ├── selection/
│   ├── prediction/
│   ├── control/
│   ├── trajectory/
│   └── timing/
│
├── behavior/
│   ├── collection/
│   ├── preprocessing/
│   ├── features/
│   ├── statistics/
│   └── visualization/
│
├── anticheat/
│   ├── rules/
│   ├── statistical/
│   ├── classical_ml/
│   ├── sequence_models/
│   ├── transformer/
│   └── ensemble/
│
├── adversarial/
│   ├── evasion/
│   ├── robustness/
│   └── adversarial_training/
│
├── benchmarks/
│   ├── vision/
│   ├── behavior/
│   ├── anticheat/
│   └── adversarial/
│
├── visualization/
│
├── experiments/
│   ├── configs/
│   ├── results/
│   └── logs/
│
├── models/
│
├── configs/
│
├── docs/
│
├── scripts/
│
├── requirements/
│
└── README.md
```

---

# 17. Copilot 协作原则

Copilot 的角色应当是：

```text
Research Assistant
+
Coding Assistant
+
Experiment Assistant
+
Data Analysis Assistant
```

而不是直接决定研究方向。

## Copilot 工作优先级

```text
1. 理解项目架构
2. 理解当前实验目标
3. 检查已有代码
4. 保持模块边界
5. 实现当前最小功能
6. 编写测试
7. 运行实验
8. 保存实验结果
9. 更新实验记录
10. 再进入下一阶段
```

## 修改代码前

Copilot 应优先：

- 阅读相关模块
- 理解数据格式
- 检查已有接口
- 检查配置
- 避免重复实现
- 避免无关重构

## 每个实验

应保持：

```text
Experiment
├── Hypothesis
├── Dataset
├── Method
├── Configuration
├── Metrics
├── Result
└── Conclusion
```

---

# 18. Research Questions

项目长期围绕以下问题展开。

### RQ1

YOLO 在真实 FPS 场景下的 Player Detection / Tracking 性能如何？

### RQ2

Human、Game Bot 和 CV Agent 的行为轨迹是否存在稳定差异？

### RQ3

哪些行为特征对 CV-based Assistance 最具有判别能力？

### RQ4

传统机器学习与深度时序模型谁更适合 Anti-Cheat？

### RQ5

当 CV Agent 主动改变行为模式后，Anti-Cheat 性能如何变化？

### RQ6

哪些特征具有较强鲁棒性？

### RQ7

Anti-Cheat 是否能够跨游戏泛化？

### RQ8

能否通过多模态行为信息提高检测能力？

---

# 19. 最终研究闭环

```text
             ┌──────────────────────┐
             │      FPS Environment │
             └──────────┬───────────┘
                        ↓
              ┌─────────────────┐
              │ Human / Bot / CV │
              └────────┬────────┘
                       ↓
                Behavior Data
                       ↓
              Feature Engineering
                       ↓
             ┌─────────┴─────────┐
             ↓                   ↓
       Rule / Classical ML   Deep Sequence
             │                   │
             └─────────┬─────────┘
                       ↓
                  Anti-Cheat
                       ↓
                  Detection
                       ↓
               Adversarial Evasion
                       ↓
                Robust Detection
                       ↓
                Cross-Game Test
                       ↓
                 Research Result
```

---

# 20. 项目最终目标

最终形成一个可复现实验平台：

```text
Game Environment
      +
Computer Vision
      +
Behavior Dataset
      +
CV Agent Simulation
      +
Anti-Cheat Models
      +
Adversarial Evaluation
      +
Cross-Game Benchmark
```

最终成果应能够回答：

> **在不依赖直接读取游戏内部状态的情况下，能否利用视觉信息与玩家行为时序特征识别 AI 辅助行为？**

以及：

> **当 AI 辅助系统主动模仿人类行为后，Anti-Cheat 如何保持鲁棒性？**

这两个问题作为整个项目的核心研究目标。