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
| M2-05 | 多目标数据采集/标注 | In Progress | `docs/MULTITARGET_DATA_TASKBOOK.md`；`tools/sample_multitarget_annotation.py`、`check_multitarget_annotation.py` | 采集 3 个新 session | 2026-11-14 |

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

---

## 10. 当前下一步

1. **Pilot、标注、感知基线与漏检分析已完成**：43 个漏检头中 small 23、clear_miss 11。
2. **当前执行 [`docs/PERCEPTION_TASKBOOK.md`](PERCEPTION_TASKBOOK.md) P2-03 方向 B**：采 3 个新 session，补 ≥150 帧多目标标注（≥60 帧 2+ head、≥20 空图）。
3. 新数据按 session 切分，90 帧 pilot test 不动；训练前先做数据质量检查。
4. 每完成一项，更新第 9.1 节状态看板与第 9.5 节变更日志。