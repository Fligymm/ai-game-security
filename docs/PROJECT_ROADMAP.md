# 项目推进书：多模态感知与测试数据采集平台

> 版本：v0.1（2026-11-14）  
> 状态：Active / Phase 0  
> 负责人：项目维护者  
> 更新节奏：每周五更新“状态看板”和“决策记录”；每次里程碑验收后更新版本号。  
> 历史架构文档 `PROJECT_FULL_ARCHITECTURE.md` 保留为背景材料，不再作为完成度依据；本文件是后续推进的唯一基线。

---

## 0. 一句话定位

把现有“FPS 瞄准/反作弊原型”收缩为一个**可复现的多模态测试数据采集与感知验证平台**：

> 同步采集屏幕视觉帧、鼠标/输入轨迹、时间戳与场景元数据，产出带 manifest、质量报告和固定切分的测试数据，并在其上验证检测/追踪等感知模块。

这个定位直接对应“多模态感知与测试数据采集”实习方向：强调**数据采集、同步、质量控制、可复现实验**，而不是继续堆叠反作弊模型或真实鼠标控制。

> **既有能力保留**：现有 `RealtimeAimLoop + Win32 hook` 已在受控 CS2 环境中验证过快速识别/自动吸附。本推进书不重写这条链路，只在其外围增加可选采集、质量检查、manifest 和感知评估；`run_real.py` 仍是显式真实控制入口。

---

## 1. 为什么调整

原项目试图同时覆盖：

- 实时视觉感知；
- 目标选择/轨迹生成；
- 真实鼠标控制；
- 行为反作弊分类；
- 对抗/隐蔽性评估。

审查结论是：范围过大，且行为数据不是 FPS 数据，99.2% 分类结果主要是生成器指纹。继续按原路线推进会得到更多“看起来很强、其实不可用”的结果。

调整后的主线：

1. **数据优先**：先建立可信、可追溯、可复现的多模态测试数据；
2. **感知验证**：在固定数据上评估检测、追踪、时序对齐；
3. **安全采集**：默认干运行，不把真实鼠标控制作为实习项目卖点；
4. **反作弊降级**：仅作为“行为数据的一种下游任务”，不再宣称已解决反作弊。

---

## 2. 范围

### 2.1 In Scope（保留并强化）

- 屏幕/视频采集：ROI、分辨率、FPS、丢帧统计。
- 输入轨迹采集：鼠标相对位移、绝对位置、时间戳、事件类型。
- 多模态同步：视觉帧与输入事件共用 monotonic 时间轴；记录同步误差。
- 测试场景矩阵：不同分辨率、UI 缩放、目标大小、运动速度、遮挡/丢失。
- 数据契约与 manifest：session/frame/input/perception 四类记录；sha256、数量、切分、许可证。
- 质量报告：FPS、时间戳单调性、同步误差、重复帧、空标签、类别分布。
- 轻量感知基线：YOLO 检测 + ByteTrack/IOU 追踪；按类别 P/R、mAP、FPS。
- 可视化/回放：把帧、框、轨迹、时间轴叠加，便于人工质检。
- 可复现实验：一条命令生成数据质量报告和感知评估报告。

### 2.2 Out of Scope（明确不做，避免简历项目失焦）

- 真实联网游戏中的自动瞄准、注入、绕过商业反作弊。
- 真实鼠标控制作为默认能力；Phase 0 后默认永远 dry-run。
- “反作弊准确率 99%”这类不可信结论；不再用代理数据训练和宣传分类器。
- DMA、Kmbox、VID/PID 伪装、硬件注入。
- 大规模 Transformer/LSTM/ensemble 训练；先做数据与基线。
- 多游戏泛化；先做单游戏/单场景的闭环。
- 实时闭环瞄准性能作为核心指标；改为“采集/感知/对齐”指标。

> **2026-11-15 范围提案：** `docs/ANTICHEAT_DEV_DRAFT.md` 提议把反作弊检测重新
> 作为“下游行为检测 benchmark”支线（先做 250 条轨迹 baseline，不重训视觉模型、
> 不接线上）。该提案待评审；在通过前，本节的 Out of Scope 仍然有效。

### 2.3 与现有框架的复用关系

| 现有模块 | 新定位 | 处理方式 |
|---|---|---|
| `vision/stream/grabber.py` | RGB 帧采集 | 保留，补时间戳、FPS/丢帧、窗口/DPI 校验 |
| `vision/stream/video_processor.py` | 离线视频感知 | 保留，作为回放/评估入口 |
| `vision/detection/yolo_detector.py` | 感知基线 | 保留，补每类阈值/评估 |
| `vision/tracking/` | 追踪基线 | 保留 ByteTrack；清理未使用的 IOU “Kalman” 命名 |
| `cv_agent/analytics/trajectory_schema.py` | 输入轨迹 schema | 保留，扩展采集元数据（不破坏旧 JSON） |
| `cv_agent/analytics/logger.py` | 输入事件记录 | 保留，补固定频率采样/事件类型 |
| `cv_agent/control/backends/csv_logger.py` | 事件/控制日志 | 保留，扩展 schema；默认只写 CSV |
| `cv_agent/trajectory/` | 合成测试夹具 | 保留，用于可控场景/回归测试，不作为真实数据 |
| `models/baseline_detector.joblib` | 旧代理基线 | 冻结，仅作历史；不再作为主结果 |
| `runs/`、YOLO 权重 | 本地产物 | 建 artifact registry；关键结果转摘要入库 |

---

## 3. 目标能力与验收指标

### 3.1 采集能力

- 单次采集 ≥ 10 分钟，目标 FPS ≥ 60；记录实际 FPS、P95 帧间隔、丢帧率。
- 视觉帧与输入事件共用 monotonic 时钟；同步误差 P95 ≤ 16 ms。
- 每个 session 有唯一 ID、场景标签、分辨率、DPI/缩放、采集时间、操作者/设备匿名 ID。
- 采集失败可恢复：断流/掉帧/热键失败均有明确状态，不静默继续。

### 3.2 数据质量

- 时间戳严格单调；重复帧率 < 1%；空标签/坏框可被质量报告发现。
- 每个数据集有 `manifest.json`：文件列表、sha256、数量、类别分布、切分、许可证。
- 固定 train/val/test；按 session/scene 分组，测试集不参与调参。
- 一条命令生成 `quality_report.json`；失败项非零退出。

### 3.3 感知基线

- 检测：每类 precision/recall/mAP50/mAP50-95；报告输入分辨率与置信度阈值。
- 追踪：至少报告 ID switch、丢失率、跟踪 FPS；不把“能跑”当“有效”。
- 对齐：检测框/轨迹与输入事件的时间偏差；可视化抽查。
- 复现：固定 seed、环境、数据 hash；报告可追溯到 commit。

### 3.4 简历可讲述的指标

- “搭建了同步 RGB + 输入轨迹 + 时间戳的多模态采集管线，采集 N 个 session / M 分钟，P95 同步误差 X ms。”
- “定义了 session/frame/input/manifest 数据契约，质量检查覆盖丢帧、重复帧、时间戳、类别分布。”
- “在固定切分上评估 YOLO/ByteTrack 基线，给出每类 P/R、mAP、FPS，并完成错误分析。”
- “默认 dry-run + fail-closed 安全采集，避免真实输入副作用。”

---

## 4. 里程碑

### M0：安全与测试闸门（当前，1–3 天）

**目标**：任何真实输入都不会因默认配置或热键失败而失控；测试不再污染工作区；特征语义可解释。

任务：

- [x] 建立本推进书，冻结旧“反作弊 99.2%”结论为代理结果。
- [x] `RealtimeLoopConfig.apply_mouse` 默认改为 `False`。
- [x] kill switch 不可用时 fail-closed，禁止真实输出。
- [x] `applied_mouse` 由后端真实能力决定；CSV-only 永远 false。
- [x] `Win32APIBackend.dry_run` 真正生效；保留 `custom_handler`/`run_real.py` Hook。
- [x] 测试全部使用临时 `model_path`；新增 `RealtimeLoop.step()` 回归测试。
- [x] 修复 `reaction_time_ms` 使用首个非零 `dx/dy` 的时间；补回归测试。
- [x] `pytest tests -q` 后 `git status` clean（除本次预期修改外）。
- [ ] Windows 真机验证 ESC/F12 注册失败路径（需要人工 smoke）。

验收：

- `RealtimeLoopConfig().apply_mouse is False`。
- kill switch 不可用时 `__enter__` 拒绝启动真实控制；`step()` 只写 CSV。
- CSV-only 后端 `applied_mouse=False`。
- 新提取的 human `reaction_time_ms` 不再全 0；首点跳变场景有测试。
- 全量测试通过，工作区干净。
- 现有 `features.json`/`evaluation_report.json` 暂不覆盖，保留为历史；M1 用新数据重算。

### M1：多模态采集 MVP（2 周）

**目标**：不替换现有 CS2 自动吸附链路，给 `RealtimeAimLoop` 增加可选的“屏幕帧 + 感知结果 + 控制事件 + 时间戳 + 元数据”同步采集。

任务：

- [x] 新增 `vision/stream/session_recorder.py`：`SessionRecorder` 写 `session.json`、`events.jsonl`、`capture.mp4`/`frames/`、`manifest.json`。
- [x] `RealtimeAimLoop` 增加 `record_dir`、`record_fps`、`record_scene` 等配置；`step()` 记录检测/选择/控制事件，默认关闭，不影响既有实盘性能。
- [x] `ScreenGrabber` 记录每帧 `last_frame_timestamp_ns`，供帧-事件对齐。
- [x] `docs/DATA_CONTRACT.md` 冻结 v0 字段。
- [x] `tools/check_session.py`：校验时间戳、计数、文件 hash、事件字段。
- [ ] 在受控 CS2 中用 `run_real.py --record-dir runs/captures --record-scene ...` 做 3 个场景各 10 分钟 pilot。
- [ ] `tools/check_dataset.py`：多 session 汇总、重复帧、类别分布、切分检查。
- [x] 回放工具 `tools/replay_session.py`：帧/视频 + 检测框 + 选中框 + 计划轨迹 + 时间戳叠加。
- [ ] 人类输入采集（`human_cs2`）：复用 recorder，但输入源改为原始鼠标/键事件；不在本 MVP 阻塞自动吸附数据。

验收：

- 自动吸附 session 采集 3 个场景（静止/慢速/快速）各 10 分钟；`manifest.json` 与质量报告生成。
- `events.jsonl` 时间戳单调；帧尺寸一致；`recorded + skipped == seen`。
- 一条命令可回放并抽查 10 个片段。
- 默认仍 dry-run；`run_real.py` 才显式进入真实控制。

### M2：测试数据 v0 与固定切分（2 周）

**目标**：形成可用于感知评估的 v0 数据集。

任务：

- 采集 ≥ 30 个 session（至少 3 个场景 × 2 个分辨率）。
- 标注/复用检测标签；建立负样本/遮挡/空场景。
- 按 session/scene 分组切分 train/val/test；生成 split manifest。
- 记录许可证/provenance；截图匿名化。
- 冻结 v0：hash、统计、质量报告、已知问题。

验收：

- 测试集完全 held out；无同 session 跨 split。
- 数据卡包含采集协议、场景矩阵、类别分布、限制。
- 质量报告无未解释失败项。

### M3：感知基线与误差分析（2 周）

**目标**：在 v0 上给出可信的检测/追踪基线。

任务：

- 训练/微调 YOLO；按类别阈值；小目标切片/放大实验。
- ByteTrack/IOU 追踪对比；报告 ID switch、丢失率、FPS。
- 帧-输入时间对齐评估；可视化错误案例。
- 固定 seed/环境；生成 `perception_report.json`。
- 错误分析：小目标、遮挡、运动模糊、UI 遮挡、分辨率。

验收：

- 每类 P/R/mAP/FPS 完整；测试集不参与调参。
- 至少 3 类典型失败案例与改进建议。
- 报告可由一条命令复现。

### M4：演示与简历包（1 周）

**目标**：把项目变成可展示、可讲述的实习作品。

交付：

- 3–5 分钟演示视频：采集 → manifest/质量报告 → 感知评估 → 回放。
- README：问题、方法、数据、指标、限制、复现命令。
- 一页简历项目描述（见第 8 节）。
- 代码/数据边界说明：默认 dry-run；不使用真实联赛/商业反作弊。

验收：

- 新用户按 README 能在 30 分钟内跑通只读 demo。
- 演示不依赖本机绝对路径/未跟踪权重。
- 所有指标能追溯到 manifest/run。

---

## 5. 数据契约（v0 草案）

> 详细字段在 M1 的 `docs/DATA_CONTRACT.md` 中冻结；这里先定边界。

### 5.1 Session

```json
{
  "session_id": "capture_20261114_001",
  "source": "screen_capture",
  "started_at_ns": 0,
  "duration_s": 600.0,
  "game": "cs2_offline",
  "scene": "static_target",
  "resolution": [2560, 1440],
  "roi": [960, 400, 640, 640],
  "dpi_scale": 1.0,
  "target_fps": 120,
  "operator_id": "anon_01",
  "modalities": ["rgb", "mouse_delta", "mouse_position", "timestamps", "game_metadata"],
  "license": "research-only"
}
```

### 5.2 Frame

- `frame_id`：单调递增。
- `timestamp_ns`：monotonic。
- `path`：相对路径。
- `width/height`：实际尺寸。
- `dropped`：是否补帧/丢帧。
- `sha256`：可选，manifest 中统一计算。

### 5.3 Input event

- `timestamp_ns`：monotonic。
- `dx/dy`：相对位移（整数）。
- `x/y`：绝对位置（可选）。
- `event`：`move` / `click` / `key` / `pause`。
- `target_id`：可选，人工/自动标注。
- `source`：`human` / `scripted_bot` / `synthetic` / `cv_agent`。

### 5.4 Manifest

- 文件列表 + sha256；
- session/frame/event 数量；
- 分辨率/场景/类别分布；
- train/val/test 及 group；
- 质量指标（FPS、同步误差、重复帧、丢帧）；
- 许可证/匿名化说明；
- 生成命令、commit、环境。

---

## 6. 评估与质量门槛

| 维度 | 指标 | 门槛（v0） |
|---|---|---|
| 采集 | 实际 FPS / P95 帧间隔 | ≥ 60 FPS；P95 ≤ 25 ms |
| 同步 | 帧-输入 P95 偏差 | ≤ 16 ms |
| 完整性 | 丢帧率 / 重复帧率 | ≤ 1% / ≤ 1% |
| 时间 | 时间戳单调 | 100% |
| 数据 | session 数 / 场景数 | ≥ 30 / ≥ 3 |
| 标注 | 每类样本 / 空标签 | 每类 ≥ 1000 框；空标签可解释 |
| 检测 | 每类 recall / mAP50 | 先报告，不设虚假高分；M3 再定 |
| 追踪 | ID switch / 丢失率 | 先报告基线 |
| 复现 | 一条命令 / 数据 hash | 必须 |

---

## 7. 风险登记册

| ID | 风险 | 概率/影响 | 缓解 |
|---|---|---|---|
| R-01 | 真实数据获取/授权失败 | 高/高 | 先用离线 demo/自录/受控场景；明确 research-only |
| R-02 | 采集与输入时间不同步 | 高/高 | 共用 monotonic 时钟；记录偏差；质量门槛 |
| R-03 | 小目标/分辨率导致检测差 | 高/高 | 切片/放大；多分辨率场景；报告限制 |
| R-04 | 数据规模不足 | 中/高 | 先做 v0 小闭环；按场景矩阵扩展 |
| R-05 | 默认真实控制引发副作用 | 中/高 | Phase 0 fail-closed；默认 dry-run；窗口守卫 |
| R-06 | 代理数据再次被误读 | 中/高 | 数据卡标注 `proxy`；禁止宣传 99.2% |
| R-07 | 范围再次膨胀 | 中/高 | 本文件 Out of Scope；每个里程碑只做验收项 |
| R-08 | 环境/GPU 不可复现 | 中/中 | 锁依赖；记录环境；CI smoke |
| R-09 | 隐私/许可证 | 中/中 | 匿名化；provenance；research-only |

---

## 8. 简历映射

### 项目名称

**多模态游戏感知与测试数据采集平台（个人项目）**

### 简历 bullet（可按实际数字替换）

- 设计并实现同步采集管线，将屏幕 RGB 帧、鼠标/输入轨迹、monotonic 时间戳与场景元数据统一到 session/frame/input 数据契约，支持 manifest 与质量报告。
- 建立数据质量门槛（FPS、丢帧、重复帧、同步误差、时间戳单调），将“能采集”推进到“可复现、可审计的测试数据”。
- 在固定切分上评估 YOLO 检测与 ByteTrack 追踪基线，输出每类 P/R、mAP、FPS 与错误分析。
- 以默认 dry-run + fail-closed 的安全设计隔离真实输入副作用；采集与回放不依赖真实游戏注入。
- 将原有“反作弊 99.2%”代理结果降级为历史基线，明确数据边界，避免不可信指标。

### 面试讲述顺序

1. 问题：FPS 感知/测试缺可复现数据，现有代理数据不可信。
2. 方法：多模态采集 + 数据契约 + 质量门槛 + 固定切分。
3. 实现：复用现有 vision/stream、schema、CSV 日志，补同步/manifest/质量报告。
4. 结果：v0 数据规模、同步误差、检测/追踪基线、失败案例。
5. 反思：小目标、域偏移、数据授权、安全边界。

---

## 9. 可持续推进机制

### 9.1 状态看板

| ID | 交付物 | 状态 | 证据 | 下一步 | 更新 |
|---|---|---|---|---|---|
| M0-01 | 推进书/范围冻结 | Done | 本文件 | 评审 | 2026-11-14 |
| M0-02 | 默认 dry-run + fail-closed | Done（单元级；交互桌面 smoke 待做） | `vision/stream/realtime_loop.py`、`safety.py`；`tests/test_control_safety.py`；本机非交互会话 RegisterHotKey 失败，符合 fail-closed | 交互桌面验证 ESC/F12 | 2026-11-14 |
| M0-03 | `applied_mouse` 真实语义 | Done | `cv_agent/control/base.py`、`win32.py`、`chained.py`、`factory.py`、`mouse.py` | 与 M1 采集日志联调 | 2026-11-14 |
| M0-04 | 测试隔离 + step 回归 | Done | `tests/test_detector.py`、`tests/test_control_safety.py`；`pytest` 40 passed | CI 化 | 2026-11-14 |
| M0-05 | 反应时间特征修复 | Done（代码级；旧 features 冻结） | `cv_agent/analytics/features.py`、`tests/test_features.py`；新提取 human 中位约 174 ms | M1 用新采数据重算；固定频率采样解决 zero-speed | 2026-11-14 |
| M1-01 | 多模态采集 MVP | Done | `runs/pilot_20261114_1920x1080`：3 场景 × ~10 分钟，53,436 帧 | 与后续数据保持一致 | 2026-11-14 |
| M1-02 | manifest/质量校验 | In Progress | 3 个 pilot 全部 `check_session` ok、warnings=[] | 多 session 汇总与数据卡 | 2026-11-14 |
| M1-03 | 数据契约 v0 | Done | `docs/DATA_CONTRACT.md` | 随 pilot 调整 | 2026-11-14 |
| M1-04 | 受控 CS2 采集 pilot | Done | `static_target` / `slow_strafe` / `fast_strafe`；总 29.74 分钟 | 质量分析后冻结 | 2026-11-14 |
| M1-05 | 回放/人工质检 | Done | `tools/replay_session.py` + `test_render_session_writes_overlay_video` | 加轨迹叠加 | 2026-11-14 |
| M1-06 | `human_cs2` 原始输入采集 | Pending | — | 全局鼠标/键事件 hook | — |
| M2-01 | 90 帧人工标注样本 | Done | `annotation/`：90 帧、280 框、6 空图；`labelstudio_to_yolo.py` `ok=true` | 扩充样本 | 2026-11-14 |
| M2-02 | 检测基线（new-environment test） | Done | `runs/eval/pilot_v0_onnx/eval_report.json`；mAP50 0.785，head-only P/R 0.860/0.695 | 错误分析 | 2026-11-14 |
| M2-03 | 漏检错误分析 | Done | `hard_examples/HARD_EXAMPLE_ANALYSIS.md`：43 个漏检头；small 23、clear_miss 11 | 多目标扩样 | 2026-11-14 |
| M2-04 | 改进方向决策 | Done | 选择方向 B：补多目标数据；见 `PERCEPTION_TASKBOOK.md` | 采 3 个新 session | 2026-11-14 |
| M2-05 | 多目标数据采集/标注 | Done（空图偏差已接受） | 150 帧、515 框、89 多目标帧；`DEVIATIONS.md`：空图 11<20 | 固定切分 | 2026-11-14 |
| M2-06 | session-level 切分与数据卡 | Done | `split_v1/`：100 train / 50 val；`split_manifest.json`；`DATASET_CARD.md`；90 帧 test 隔离 | 微调实验 | 2026-11-14 |
| M3-01 | 多目标微调 | Done（候选） | `cs2_multitarget_ft_v1`；90 帧 test：mAP50 0.919，head mAP50 0.922，head R@0.35 0.780；全部门槛通过；`FINETUNE_EVAL.md` | live dry-run | 2026-11-14 |
| M3-02 | 部署候选 live 验证 | Done | 短时 live dry-run 通过（定性；FPS/选中稳定性/ROI/空背景）；新 ONNX 设为 `run_real.py` 默认权重 | 多场景 pilot | 2026-11-14 |
| M3-03 | 旧 pilot 视频离线回放对比 | Done（初版） | `tools/compare_replay_models.py`；8,863 帧、3 场景；新模型 boxes +24.9%、empty -60.1%、jump +33.6%；报告 `replay_v1_vs_v0/REPLAY_REVIEW.md` | contact sheet 抽检 | 2026-11-14 |
| M3-04 | 回放分歧帧人工复核 | Done | 项目所有者复核 contact sheets 后确认模型可收尾，不再补数据；`REPLAY_REVIEW.md` | 收尾/开源准备 | 2026-11-14 |
| M3-05 | 模型收尾与开源准备 | Done | `MODEL_CARD.md`、`MODEL_MANIFEST.json`、`docs/OPEN_SOURCE_CHECKLIST.md`；R2 已修复；MIT 许可证；白名单已推送 `release/research-whitelist`（`769e2d6`） | 后续合规维护 | 2026-11-15 |
| M4-01 | 反作弊行为检测开发草案 | Draft v0.2.1；P0-A approved | `docs/ANTICHEAT_DEV_DRAFT.md`：按学术评审改为 P0 真实 FPS 数据 + 视觉-行为对齐 + held-out 协议；现有 proxy AUC 仅作对照 | 批准 P0-B pilot | 2026-11-15 |
| M4-02 | P0-A 标签/威胁模型协议 | Done | `docs/ANTICHEAT_LABEL_PROTOCOL.md`：H/B/C/X 定义、采集边界、数据 schema、切分与隐私规则；项目所有者批准 | 启动 2–3 session P0-B pilot | 2026-11-15 |
| M4-03 | P0-B pilot 工具与预检 | Tooling upgraded / data blocked | 窗口采集 `window_capture.py`、生命周期、`check_fps_pilot` 独立状态、C 离线 dry-run；当前无 CS2/人类参与者 | 在真实离线环境执行 H/B pilot | 2026-11-15 |
| M4-04 | R2 抓屏与实验流程升级 | H/B pilot + tiled C dry-run passed | `p0b_human_20261116_152512`、`p0b_game_bot_20261116_152746` 通过 timebase；3×3 tiling 后 H 759/1604、B 1124/1641 帧有检测；输出关联 source/video/model SHA | P0-C 特征分析/扩大采集 | 2026-11-16 |
| M4-05 | P0-C tiled 特征 pilot | QC automation done; human review pending | `runs/eval/anticheat_p0c/pilot_tiled_v1`、`docs/research/P0C_PILOT_FEATURES.md`；head 检测仅 3/7，选中 run 中位数 2 帧；contact sheets 已生成 | 人工复核 contact sheets；暂不扩样 | 2026-11-16 |
| M4-06 | P0-C old/new 模型 POV 对比 | Done（descriptive） | `docs/research/P0C_MODEL_COMPARISON.md`；同一 H/B tiled 配置下 old head 183/185，new head 3/7 | 逐框对照 | 2026-11-16 |
| M4-07 | 默认模型回退与旧数据审计 | Done | `run_real.py` 默认回退 old；`docs/research/P0B_MODEL_DEFAULT_DECISION.md`；旧 v2 数据 135/135、33/33 平衡且无缺标签 | 旧模型 P0-C 复检 | 2026-11-16 |
| M4-08 | old 模型 P0-C 特征/QC | QC passed | `docs/research/P0C_OLD_PILOT_FEATURES.md`；old head 132/129，offset 80.7/106.8；所有者确认目标覆盖和跟踪通过，碎片化来自目标短时存在 | 扩到每类 3 个独立 session | 2026-11-16 |
| M4-09 | P0-C 扩样请求 | Done | 新增 H-02/H-03/B-02/B-03；4 个新 session `check_fps_pilot --verify-hash` 均通过 timebase | 新 session 人工 QC | 2026-11-16 |
| M4-10 | 3H/3B old-model P0-C 特征 | Descriptive only | `docs/research/P0C_3X3_FEATURES.md`、`runs/eval/anticheat_p0c/pilot_old_tiled_v2`；head/body 比例恢复，H/B 覆盖范围重叠 | 新 session QC | 2026-11-16 |
| M4-11 | 3H/3B 简单 baseline | Negative pilot | `docs/research/P0C_BASELINE.md`、`runs/eval/anticheat_p0c/baseline_v2`；Logistic 4/6，RF 2/6，不能作为分类结论；body 漏检 accepted limitation | 扩样后再 baseline；不调参 | 2026-11-16 |
| M4-12 | 第二轮扩样 3H/3B -> 5H/5B | Done | `docs/ANTICHEAT_P0C_EXPANSION_ROUND2.md`；4 个新 session 通过；B-04 由 `214446` 补录 | 5H/5B baseline | 2026-11-16 |
| M4-13 | 5H/5B P0-C 特征与 baseline | Negative pilot | `docs/research/P0C_5X5_FEATURES.md`；Logistic/RF 6/10，AUC 0.68/0.72；仍不可靠 | 不调参；转 Feature v2 | 2026-11-16 |
| M4-14 | P0-C Feature v2 草案/首轮 | Implemented; conditional signal | `docs/research/P0C_FEATURE_V2_DRAFT.md`、`P0C_FEATURE_V2_RESULTS.md`；F2 tracking RF AUC 0.92，其他家族弱；10 sessions 仍小 | 固定 F2 后扩到 10H/10B 验证 | 2026-11-16 |
| M4-15 | 第三轮扩样 5H/5B -> 10H/10B | Done | 实际 11H/10B；全部 timebase PASS；old C tiled 完成 | 固定 F2 验证 | 2026-11-16 |
| M4-16 | 固定 F2 10H/10B 验证 | Invalidated by map confound | `P0C_FEATURE_V2_10X10.md`；6 个 H 为新地图，B 全旧地图 | 隔离新地图 H | 2026-11-16 |
| M4-17 | F2 confounder 分析 | Invalidated by map confound | `P0C_CONFOUNDER_ANALYSIS.md`；可见性/目标大小 + 地图混入 | 旧地图 5H/5B 复检 | 2026-11-16 |
| M4-18 | 地图 confound 审计/标签修正 | Labeled; blocked on data | `docs/research/P0C_MAP_CONFOUND.md`；旧 15 = dust2，新 6H = aim_botz；11H/10B 作废；旧 dust2 5H/5B F2 AUC 0.88/residual 0.64 | 请求 5 个 dust2 H | 2026-11-17 |

### 9.2 每周节奏

- **周一**：从看板选 1 个 M 级别的最小验收项；写清“本周只做什么”。
- **周三**：中途检查；若发现范围膨胀，记录到决策日志并砍掉非验收项。
- **周五**：更新看板；跑 `pytest` + 质量报告；把证据链接写到“证据”列。
- **每两周**：复盘一次“是否仍服务于多模态感知/测试数据采集方向”；不服务就移出范围。

### 9.3 Definition of Done

一个任务只有同时满足以下条件才标 Done：

- 有代码/文档/数据产物；
- 有可执行验收（测试/命令/报告）；
- 有证据链接（文件/指标/截图）；
- 不破坏 AGENTS 的安全约束；
- 更新了状态看板和变更日志。

### 9.4 决策记录

| ID | 日期 | 决策 | 理由 |
|---|---|---|---|
| D-001 | 2026-11-14 | 项目主线改为“多模态感知与测试数据采集” | 匹配实习方向；原反作弊范围过大且数据不可信 |
| D-002 | 2026-11-14 | 真实鼠标控制移出主线，默认 dry-run | 安全与伦理；实习项目不需要真实注入 |
| D-003 | 2026-11-14 | 现有 251 条行为数据保留为 `proxy` | 可复现的特征/管线仍有价值，但不能作为最终结论 |
| D-004 | 2026-11-14 | 反作弊模型降级为下游可选项 | 先完成数据/感知闭环，避免继续堆模型 |
| D-005 | 2026-11-15 | 反作弊检测重新作为下游研究支线提案，待评审；v0.2 要求真实 FPS 数据与视觉-行为对齐 | 学术评审指出 proxy 数据不能支撑 FPS 反作弊结论 |

### 9.5 变更日志

- 2026-11-14：建立 v0.1 推进书；冻结范围；开始 M0。
- 2026-11-14：完成 M0 单元级修复：默认 dry-run、kill switch fail-closed、`applied_mouse` 能力语义、测试隔离、`step()` 回归、反应时间特征修复；`pytest` 40 passed。
- 2026-11-14：保留 `zero_speed_fraction` 的已知限制：事件式采集无法表示停顿；M1 改为固定频率采样后补齐。
- 2026-11-14：M1 采集 MVP 接入现有 `RealtimeAimLoop`：可选 `record_dir` 写 `session.json`/`events.jsonl`/`capture.mp4`/`manifest.json`；保留 CS2 自动吸附链路。
- 2026-11-14：新增 `docs/DATA_CONTRACT.md` v0；`ScreenGrabber` 增加帧时间戳；`run_real.py` 显式补 `--apply-mouse`，不破坏既有真实入口。
- 2026-11-14：新增 `tools/check_session.py` 与测试；校验事件计数、时间戳、帧文件/视频、manifest 文件与 sha256。
- 2026-11-14：新增 `tools/replay_session.py`，把检测框/选中目标/计划轨迹/时间戳叠加到回放视频，支持人工质检。
- 2026-11-14：安全 smoke 记录：当前自动化非交互会话中 `RegisterHotKey` 失败，`is_running=False`，真实控制按设计拒绝；需在交互桌面复核。
- 2026-11-14：dry smoke 发现 `record_fps=30` 在帧突发时抽样丢帧（183/300，effective_fps 15.7）；`SessionRecorder` 改为 `video_fps >= target_fps` 时不抽样，并钳制回放 FPS；新增回归测试。
- 2026-11-14：真实 smoke 发现 F12 已被其他程序注册（Win32 error 1409）；`GlobalHotkeyKillSwitch` 增加 `GetAsyncKeyState` 轮询兜底，保留 ESC/F12 语义，新增轮询测试。
- 2026-11-14：完成 1920x1080 窗口模式的 3 场景 pilot（static/slow/fast），总 53,436 帧、29.74 分钟，全部 check ok；采集几何为 2560x1440 桌面中心 ROI。
- 2026-11-14：新增 `tools/sample_annotation.py`，从 3 个 pilot 分层抽取 90 帧（60 有模型选中 / 30 无选中），生成 `annotation/` 与标注说明；尚未标注。
- 2026-11-14：新增 `tools/labelstudio_to_yolo.py` 与 `annotation/README.md`，固定 Label Studio 1.23 的 90 帧标注流程、`enemy_head`/`enemy_body` 配置及 JSON→YOLO 转换。
- 2026-11-14：完成 90 帧人工标注（280 框、6 空图）与部署 ONNX 基线：mAP50 0.785，conf=0.35 全类 P/R 0.910/0.718，head-only 0.860/0.695；详见 `PERCEPTION_EVAL.md`。
- 2026-11-14：新增 `docs/PERCEPTION_TASKBOOK.md`；完成 43 个漏检头人工分型，输出 `HARD_EXAMPLE_ANALYSIS.md`：small 23、clear_miss 11；clear_miss 中 9/11 发生在 2–4 头多目标帧，决定优先补多目标数据。
- 2026-11-14：新增 `docs/MULTITARGET_DATA_TASKBOOK.md`、`tools/sample_multitarget_annotation.py`、`tools/check_multitarget_annotation.py`，固定多目标补采、抽样、标注和验收流程。
- 2026-11-14：完成多目标标注 150 帧：515 框（head 259 / body 256）、89 个多目标帧、11 个空图、3 个 session；Label Studio 重复 task 10 个，用 `tools/dedupe_labelstudio_export.py` 去重后转换 `ok=true`。空图 11 < 20，已记录偏差并决定进入切分准备，不把它当零误报证据。
- 2026-11-14：新增 `tools/split_multitarget_dataset.py` 与 `split_v1`（100 train / 50 val，90 帧 test 隔离、无 hash/session 泄漏），生成 `DATASET_CARD.md`/`DEVIATIONS.md`；新增 `configs/finetune_multitarget_v1.yaml`、`tools/finetune_multitarget.py`（默认 dry-run）和 `TRAINING_RECORD.md`，尚未训练。
- 2026-11-14：完成 `cs2_multitarget_ft_v1` 微调（best epoch 26，早停于 41）；90 帧 test 上 ONNX mAP50 0.919（旧 0.785）、head mAP50 0.922（旧 0.745）、head R@0.35 0.780（旧 0.695），空图 FP 0/6；导出 `best.onnx`。
- 2026-11-14：短时 live dry-run 通过；新 ONNX 设为 `run_real.py` 默认权重，显式 `--weights` 仍可回滚到旧 `cs2_detection_v2/best.onnx`；新增默认权重单元测试。
- 2026-11-14：新增 `tools/compare_replay_models.py`，复用 3 个 pilot 视频做 8,863 帧旧/新 ONNX 回放；新模型 boxes +24.9%、empty frames -60.1%、new-only 6,483、jump +33.6%，延迟持平；生成 `replay_v1_vs_v0/REPLAY_REVIEW.md` 与三张分歧 contact sheet。
- 2026-11-14：项目所有者复核 contact sheets 后确认模型可收尾，不再补数据；新增 `MODEL_CARD.md`、`MODEL_MANIFEST.json`（权重/证据哈希）和 `docs/OPEN_SOURCE_CHECKLIST.md`，进入开源准备阶段。
- 2026-11-14：模型冻结后 R1–R4 定向审核完成；R1 部署/回滚 PASS；R2 发现 `AimController.log_only()` 仍向真实后端发送移动，已修复为 logging-only 路径并新增 stopped/paused 回归测试（`test_control_safety.py` 13 passed），项目所有者物理 ESC/F12 验证通过；R3/R4 保留隐私与许可证缺口，详见 `docs/FINAL_RISK_REVIEW_2026-11-14.md`。
- 2026-11-14：新增 `docs/ACADEMIC_USE_NOTICE.md`，明确禁止违法用途、仅限学习/教学/学术研究；该声明不替代许可证，也不授予发布权。
- 2026-11-14：新增 `docs/LEGAL_AND_ETHICS.md`，按所有者的法律风险分析记录刑/行/民边界、VDP 科研规范和红线；新增 `docs/RELEASE_WHITELIST.md` 和 `RIGHTS.md`，授权范围限定为文档、模型卡/清单、聚合指标和 MIT 许可声明，不含代码、权重、原始数据或 contact sheets。已生成并扫描本地白名单归档，记录见 `docs/RELEASE_BUILD_RECORD.md`，未上传。
- 2026-11-14：新增根 `LICENSE`，采用 MIT，`Copyright (c) 2026 Fligymm`；`RIGHTS.md` 说明 MIT 仅覆盖项目代码/文档，权重、游戏画面/标注和第三方材料不在授权范围内。
- 2026-11-15：新增 `docs/ANTICHEAT_DEV_DRAFT.md`，提案以现有 250 条 human/bot/synthetic 轨迹建立反作弊检测 MVP；当前仅草案，未改代码、模型或控制链路。
- 2026-11-15：根据 `docs/research/ACADEMIC_FEASIBILITY_REVIEW.md` 更新草案至 v0.2：现有 proxy baseline/AUC 仅作对照，P0 改为真实 FPS 数据、视觉-行为对齐和 held-out 协议。
- 2026-11-15：P0-A 标签/威胁模型协议 `docs/ANTICHEAT_LABEL_PROTOCOL.md` 完成并由项目所有者批准；尚未采集数据或修改代码。
- 2026-11-15：P0-B pilot 工具完成：`capture_fps_pilot.py` / `check_fps_pilot.py` / 4 tests；当前无 CS2/人类参与者，未采集、未伪造数据。
- 2026-11-15：R2 抓屏升级：新增指定窗口 fail-closed 抓屏、生命周期、POV/attestation 字段、视频/哈希独立校验和 C 离线 dry-run 工具；真实 H/B/C 验证仍待环境。
- 2026-11-16：修复中文标题 CS2 被 `Counter-Strike 2` 字符串漏检的问题；窗口识别改为优先按 `cs2.exe` 进程匹配，真实窗口单帧 1920x1080 抓取通过。
- 2026-11-16：增加 `--focus-window`（默认开启），解决从终端启动时 PowerShell 抢前台导致 CS2 被判定非前台的问题；焦点切换后单帧抓取通过。
- 2026-11-16：首个真实 H pilot session `p0b_human_20261116_112054` 采集完成；文件/视频/POV 状态通过，但实际约 26.3 fps，视频 78.88s 短于 session 180.03s，`TIMEBASE_CONSISTENT=false`，不能作为最终时序数据。
- 2026-11-16：采集默认 `--fps` 改为 30（1920×1080 mss 实测更稳定）；`check_fps_pilot` 新增 `TIMEBASE_CONSISTENT`，时长偏差超过 20% 直接判失败；现有 60fps pilot 需按 30fps 重录。
- 2026-11-16：新 H/B pilot（`p0b_human_20261116_152512`、`p0b_game_bot_20261116_152746`）通过 timebase；C 离线 dry-run 完成，输出 source/video/model SHA 与 `capture_time_s`。
- 2026-11-16：C 离线推理增加 3×3/720 `TiledDetector`；同一 H/B 视频检测覆盖从 43/1604、150/1641 提升到 759/1604、1124/1641，671/908 帧选中并写入 CSV。
- 2026-11-16：P0-C tiled 特征 pilot 完成（`docs/research/P0C_PILOT_FEATURES.md`）：H/B 各 1 session，body 选中占绝对多数，track switch 偏高；当前仅描述性，不训练分类器。
- 2026-11-16：P0-C 自动 QC 与 contact sheets：head 仅 3/7 个检测，selected run 中位数 2 帧；人工视觉复核待做，暂不扩数据集。
- 2026-11-16：old/new 同 H/B POV 对比：old head 183/185，new head 3/7；new 在原 90 帧 320 ROI 测试仍更优。记录为 POV 域/尺度风险。
- 2026-11-16：项目所有者决定默认回退 old：`run_real.py` 与 C 离线工具默认 `cs2_detection_v2/weights/best.onnx`；new 保留候选。旧 v2 数据审计未发现类别失衡或缺标签（train 135/135，val 33/33）。
- 2026-11-16：old 模型 P0-C 复检完成：head 132/129，offset 80.7/106.8，track episode 93/89；contact sheets 已生成。
- 2026-11-16：所有者人工 QC 通过：H/B 目标覆盖好、跟踪时间符合要求；碎片化归因于目标存在时间短。请求新增 H-02/H-03/B-02/B-03，扩到每类 3 个独立 session。
- 2026-11-16：4 个新 session 采集并通过 timebase；old-model tiled C 与 3H/3B P0-C 特征完成（`P0C_3X3_FEATURES.md`）。
- 2026-11-16：3H/3B leave-one-session-out baseline（`P0C_BASELINE.md`）：Logistic 4/6、RF 2/6、Dummy 3/6；当前特征不可分类。body 少量漏检因样本少/姿态变化，记录为 accepted limitation。
- 2026-11-16：第二轮扩样脚本 `scripts/capture_p0b_expansion.ps1` 完成（H-04/H-05/B-04/B-05，目标 5H/5B）；不训练分类器，等待采集。
- 2026-11-16：H-04/H-05/B-05 通过校验；B-04 因游戏窗口失焦在 55.6s 被 fail-closed 中止，保留为 aborted，不用于分析。
- 2026-11-16：B-04 由 `p0b_game_bot_20261116_214446` 补录并通过；完成 5H/5B 特征与 baseline（Logistic/RF 6/10），仍不支持可靠分类。
- 2026-11-16：P0-C Feature v2 草案完成：F1 目标获取、F2 跟踪、F3 修正、F4 切换、F5 可见性；先用 5H/5B 做 go/no-go，不扩数据、不训练。
- 2026-11-16：Feature v2 首轮 5H/5B 完成：F2 tracking 单独 RF AUC 0.92，其他家族弱；条件性 signal，仍需 10H/10B 验证；不训练分类器。
- 2026-11-16：新增第三轮扩样请求 `ANTICHEAT_P0C_EXPANSION_ROUND3.md`：H-06..H-10 / B-06..B-10，固定 F2 特征，不重新选特征。
- 2026-11-16：第三轮实际完成 11H/10B；固定 F2 LOO Logistic 0.857 / AUC 0.918，错误跨 3 个 session。
- 2026-11-16：F2 confounder 分析完成：confounders-only AUC 0.945，F2 residualized AUC 0.645；F2 主要编码可见性/目标大小，不是行为差异。暂停分类器与同条件扩样。
- 2026-11-16：发现 22:33–22:45 的 6 个 H 属于不同地图，B 全为旧地图；11H/10B F2 结果作废。旧地图 5H/5B F2 AUC 0.88/residual 0.64。
- 2026-11-17：地图标签修正：旧 15 个 session = dust2，6 个新 H = aim_botz；`session.json` 与 `manifest.json` 同步，manifest SHA 重算；请求 5 个 dust2 H。

---

## 10. 当前下一步

1. **Pilot、标注、感知基线与漏检分析已完成**：43 个漏检头中 small 23、clear_miss 11。
2. **P2-03 方向 B 数据已完成**：150 帧多目标标注、89 个多目标帧、515 框；空图 11，记录偏差后继续。
3. 微调已完成 `cs2_multitarget_ft_v1`；90 帧 test 全部门槛通过，新 ONNX 已设为 `run_real.py` 默认权重，短时 live dry-run 已通过，详见 `runs/pilot_20261115_multitarget/FINETUNE_EVAL.md`。
4. 旧/新 ONNX 回放（8,863 帧）已完成，项目所有者复核 contact sheets 后确认模型可收尾，不再补数据；旧 `cs2_detection_v2/best.onnx` 保留回滚。
5. 开源准备已完成：MIT 许可证、研究披露白名单已推送到 `release/research-whitelist`；后续只做合规维护，不重推完整工作树。
6. 反作弊检测作为下游支线：先评审 `docs/ANTICHEAT_DEV_DRAFT.md`，通过后只做 W1–W2 MVP（数据审计 + baseline），不重训视觉模型、不接线上。
7. 每完成一项，更新第 9.1 节状态看板与第 9.5 节变更日志。