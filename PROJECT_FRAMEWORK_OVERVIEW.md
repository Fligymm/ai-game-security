# AI Game Security Lab 功能框架说明

本文档用于给其他 LLM 或协作人员快速理解项目结构，只描述模块职责、边界和数据流，不包含任何实现细节。

## 1. 项目目标

项目围绕游戏画面理解、目标识别、行为轨迹建模、辅助行为模拟和反作弊检测展开，主要用于离线、合法、可控环境下的研究与实验。

核心关注点包括：

- 视觉目标识别
- 目标筛选与位置估计
- 轨迹生成与鼠标行为模拟
- 行为数据采集与特征提取
- 反作弊检测与鲁棒性评估
- 对抗扰动与鲁棒检测研究

## 2. 总体模块划分

### 2.1 `vision`

视觉处理总层，负责从视频、摄像头或屏幕流中获取图像，并完成检测、追踪和可视化相关工作。

- `vision.detection`：目标检测模块，输出框、置信度和类别信息。
- `vision.stream`：视频流处理模块，负责读取视频帧、调用检测器、维护轨迹和预览结果。
- `vision.tracking`：追踪相关命名空间，表示未来可扩展的多目标关联能力。
- `vision.prediction`：视觉侧预测命名空间，表示未来可扩展的短期运动预测能力。
- `vision.benchmark`：视觉任务评估入口，用于检测、追踪等能力的对比测试。

### 2.2 `cv_agent`

CV Agent 模块，负责把视觉检测结果转化为可用于目标选择、路径规划和鼠标行为模拟的研究对象。

- `cv_agent.detection`：把检测框转成目标状态，重点表达目标相对屏幕中心的偏移。
- `cv_agent.selection`：目标选择模块，从多个候选目标里挑选优先级最高的一个。
- `cv_agent.prediction`：短期运动预测模块，用于估计目标下一步位置或偏移趋势。
- `cv_agent.trajectory`：轨迹生成模块，提供多种鼠标/视角路径风格，用于模拟和分析。
- `cv_agent.timing`：时间步长和采样节奏相关模块，用于控制轨迹执行节奏。
- `cv_agent.control`：控制输出模块，负责把规划好的轨迹转成相对鼠标动作或实验中的执行结果。

### 2.3 `behavior`

行为分析模块，负责采集、清洗、统计和展示玩家或代理的行为数据。

- `behavior.collection`：数据收集与数据集拆分。
- `behavior.preprocessing`：行为数据预处理与清洗。
- `behavior.features`：行为特征工程与特征构造。
- `behavior.statistics`：统计分析、分布总结和行为指标计算。
- `behavior.visualization`：行为数据可视化。

### 2.4 `anticheat`

反作弊研究模块，承载不同层次的检测思路。

- `anticheat.rules`：规则型检测思路。
- `anticheat.statistical`：统计异常检测思路。
- `anticheat.classical_ml`：传统机器学习检测思路。
- `anticheat.sequence_models`：序列建模检测思路。
- `anticheat.transformer`：Transformer 类模型检测思路。
- `anticheat.ensemble`：多模型集成检测思路。

### 2.5 `adversarial`

对抗研究模块，用于研究检测规避、扰动和鲁棒性问题。

- `adversarial.evasion`：规避策略研究。
- `adversarial.robustness`：鲁棒性研究。
- `adversarial.adversarial_training`：对抗训练相关研究。

### 2.6 `benchmarks`

基准测试模块，用于统一比较不同子系统的效果。

- `benchmarks.vision`：视觉能力基准。
- `benchmarks.behavior`：行为分析基准。
- `benchmarks.anticheat`：反作弊检测基准。
- `benchmarks.adversarial`：对抗研究基准。

### 2.7 `visualization`

实验可视化模块，负责把检测框、偏移量、轨迹或分析结果叠加到图像上，便于人工观察和汇报。

## 3. 关键脚本与入口

- `train.py`：训练入口，用于训练检测模型。
- `test_onnx.py`：ONNX 推理测试入口。
- `test_video.py`：视频推理测试入口。
- `scripts/offset_visualize.py`：偏移分析与轨迹展示入口。
- `scripts/mouse_lock_smoke.py`：短期鼠标锁定与轨迹分类测试入口。

## 4. 数据与资源目录

- `datasets`：训练、验证、实验和行为数据存放位置。
- `models`：模型产物与保存目录。
- `weights`：预训练权重或本地权重文件。
- `runs`：训练、预测和分析输出结果。
- `experiments`：实验配置、日志和结果归档。

## 5. 典型数据流

### 5.1 视觉到控制的主链路

1. 输入来自视频、摄像头或屏幕流。
2. `vision.detection` 输出检测框。
3. `cv_agent.detection` 将检测框转成目标状态。
4. `cv_agent.selection` 选出优先目标。
5. `cv_agent.prediction` 估计短期目标偏移。
6. `cv_agent.trajectory` 生成候选轨迹。
7. `cv_agent.control` 根据轨迹给出执行结果或鼠标动作。

### 5.2 行为分析与反作弊链路

1. 收集鼠标、视角、目标、射击等行为数据。
2. 进行预处理和标准化。
3. 抽取时间序列与统计特征。
4. 输入规则、统计模型或机器学习模型。
5. 得到异常评分、分类结果或鲁棒性评估结论。

## 6. 模块边界说明

- `vision` 更偏输入和识别，不负责策略选择。
- `cv_agent` 更偏决策与轨迹，不直接承担数据训练。
- `behavior` 更偏特征和分析，不依赖单一视觉实现。
- `anticheat` 更偏判别和建模，不负责原始数据采集。
- `adversarial` 更偏研究对抗关系，不作为默认生产路径。
- `benchmarks` 用于统一比较，不承担核心业务逻辑。

## 7. 给其他 LLM 的使用建议

如果要让其他 LLM 辅助编程，建议优先按下面顺序理解项目：

1. 先看 `vision` 和 `cv_agent` 的数据流。
2. 再看 `behavior` 与 `anticheat` 的特征和检测接口。
3. 最后看 `adversarial`、`benchmarks` 和 `visualization` 作为研究辅助层。

该项目当前更适合被理解为“研究型框架”，而不是单一业务应用。拆任务时应优先按模块职责分开提问，避免把检测、控制、训练和评估混在一起。