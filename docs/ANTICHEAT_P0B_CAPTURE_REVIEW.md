# P0-B-R2-A：现有抓屏与实验流程审查

日期：2026-11-15  
状态：**R2-A review complete；R2-B/C/D 已按本设计实现，待真实环境验证**  
范围：抓屏、POV 元数据、session 生命周期、校验、CV Agent 离线视频能力。

---

## 1. 现有实现

### 1.1 采集入口

[`tools/capture_fps_pilot.py`](../tools/capture_fps_pilot.py) 当前：

- 使用 [`ScreenGrabber`](../vision/stream/grabber.py)；
- 默认抓取**显示器中心固定 ROI**，不是指定窗口；
- 使用 [`SessionRecorder`](../vision/stream/session_recorder.py) 写
  `session.json` / `events.jsonl` / `capture.mp4` / `manifest.json`；
- `--agent-type` 只写入 `extra.agent_type`；
- `record_frame()` 固定写入空检测、无选中、`applied_mouse=false`；
- 不启动 CS2、不启动 Agent、不读取 Agent 输出、不捕获输入。

### 1.2 校验入口

[`tools/check_fps_pilot.py`](../tools/check_fps_pilot.py) 当前：

- 复用 [`tools/check_session.py`](../tools/check_session.py)；
- 校验 `agent_type`、`is_proxy`、`real_control`、`capture_mode`、
  `protocol_version`；
- 校验 manifest/hash、事件帧数、时间戳；
- 不校验实际视频分辨率、实际时长、平均 FPS、窗口/POV 来源。

### 1.3 离线视频能力

[`vision/stream/video_processor.py`](../vision/stream/video_processor.py) 支持：

- 打开视频文件；
- `YOLODetector` 逐帧检测；
- 简单中心点轨迹关联；
- 预览/轨迹输出。

但它**不是完整 CV Agent**：

- 没有 `TargetSelector`；
- 没有 Kalman/预测；
- 没有轨迹规划；
- 没有 `AimController`；
- 没有逐帧决策 JSONL；
- 没有源视频 session/hash/模型版本元数据；
- 没有 `dry_run` 标记。

[`vision/stream/realtime_loop.py`](../vision/stream/realtime_loop.py) 是完整链路，但它面向**屏幕实时输入**，不是视频文件输入。

结论：**现有代码支持“视频检测/轨迹预览”，不支持“完整 CV Agent 离线 dry-run 关联”。**

---

## 2. 主要缺陷

| ID | 缺陷 | 影响 | 严重度 |
|---|---|---|---|
| C1 | 使用显示器中心 ROI，而非目标窗口 | 可能录到桌面/其他窗口 | **BLOCKER for POV** |
| C2 | 不检查 CS2 进程/窗口 | 无窗口时仍可能录桌面 | **BLOCKER** |
| C3 | 不检查最小化/失焦/遮挡 | 可能录到黑屏/桌面 | HIGH |
| C4 | 无 POV 来源字段 | 无法区分 H/B | **BLOCKER** |
| C5 | 无 session 生命周期事件 | 异常退出不可复核 | HIGH |
| C6 | 校验不检查视频分辨率/时长/FPS | 文件存在≠有效视频 | HIGH |
| C7 | 校验状态不可区分 | 文件完整性、解码、窗口、人工确认混淆 | HIGH |
| C8 | 完整 CV Agent 无离线视频入口 | C 实验无法执行 | **BLOCKER for C** |
| C9 | 无源视频 session/hash 关联 | 推理结果不可追溯 | HIGH |
| C10 | `--agent-type` 只是标签 | 不能证明实验对象 | ACCEPTED（需人工确认） |

---

## 3. 必须修改的代码

### 3.1 新增窗口采集

新增 `vision/stream/window_capture.py`：

- Windows `EnumWindows` 按 **`cs2.exe` 进程**识别 CS2 窗口，标题只作回退；
  这避免中文标题 `反恐精英：全球攻势` 被 `Counter-Strike 2` 字符串漏掉；
- 校验 `IsWindowVisible`、`IsIconic`、`GetForegroundWindow`；
- 使用 `GetClientRect` + `ClientToScreen` 获取**客户端区域**；
- 使用 `mss` 抓取该区域；
- 每帧重新校验窗口仍存在、可见、未最小化、前台、尺寸不变；
- 失败时抛出明确异常，**不降级为桌面抓屏**。

限制：

- 不保证 DirectX 独占全屏/受保护内容；
- 不保证被其他窗口遮挡时的内容（因为要求前台）；
- HDR/DPI 缩放需要实测；
- 不使用 `PrintWindow`/注入，避免不可靠和越界。

### 3.2 采集工具升级

修改 `tools/capture_fps_pilot.py`：

- 只允许 `human`、`game_bot`；
- 要求显式 `--capture-source`：
  - `human` -> `player_pov`
  - `game_bot` -> `observer_followed_bot`
- 要求显式 `--view-mode first_person`；
- 要求 `--attest-pov` 和 `--attest-experiment`；
- 使用 `WindowCapture`，不再使用中心 ROI；
- 写入生命周期 `lifecycle.jsonl`；
- 记录窗口信息、视频路径/大小/哈希、状态；
- 异常时写 `capture_aborted`，不伪造 `experiment_finished`；
- 保留 `SessionRecorder`、CSV/flush、安全边界。

### 3.3 校验工具升级

修改 `tools/check_fps_pilot.py`：

- 保留 base `check_session`；
- 增加：
  - 视频解码、实际分辨率、时长、平均 FPS；
  - 必要字段；
  - `view_mode`/`capture_source` 组合；
  - 生命周期事件顺序；
  - 视频 SHA256；
- 返回独立状态：

```text
FILE_INTEGRITY_VERIFIED
VIDEO_DECODE_VERIFIED
GAME_WINDOW_OBSERVED
POV_MANUALLY_ATTESTED
EXPERIMENT_MANUALLY_ATTESTED
TIMEBASE_CONSISTENT
```

### 3.4 CV Agent 离线入口

新增 `tools/run_cv_agent_offline.py`：

- 输入已通过校验的 H/B session；
- 读取原始视频，不修改；
- 复用 `YOLODetector -> AimPipeline -> CSV`；
- `apply_mouse=False`，禁止真实控制；
- 输出逐帧 JSONL、决策 CSV、推理元数据；
- 记录源 session_id、源视频 SHA256、模型路径/哈希、配置；
- 标记 `dry_run=true`。

如果完整离线入口不能在最小范围内稳定实现，则先输出设计，不伪造结果。

### 3.5 文档

更新：

- `docs/ANTICHEAT_P0B_PILOT.md`：H/B/C 新版流程；
- `docs/ANTICHEAT_P0B_AGENT_READINESS.md`：状态更新；
- `docs/ANTICHEAT_P0B_CAPTURE_REVIEW.md`：本文件。

---

## 4. 可以保留的代码

- `ScreenGrabber`：回放/屏幕调试保留，但不再用于 P0-B 正式采集；
- `SessionRecorder`：保留，继续负责 frame/events/manifest；
- `check_session.py`：保留为基础完整性检查；
- `AimPipeline`/`RealtimeAimLoop`/`AimController`：保留，不改控制语义；
- `YOLODetector`：保留；
- `CSVLoggerBackend`/`flush`：保留；
- 现有测试与发布边界：保留。

不修改：

```text
cv_agent/control/*
run_real.py
模型权重
训练/标注数据
```

---

## 5. 建议的最小实现方案

1. `WindowCapture` 只做“窗口客户端区域 + 前台校验”的桌面合成抓取；
2. 采集工具 fail-closed：窗口不存在/最小化/失焦/尺寸变化时退出，不录桌面；
3. 生命周期写 sidecar JSONL，`SessionRecorder` 继续写主 manifest；
4. `check_fps_pilot` 把文件完整性、解码、窗口、人工确认拆成独立状态；
5. CV 离线工具只复用现有 `AimPipeline`，`apply_mouse=False`，写逐帧 JSONL；
6. 所有测试使用合成视频/临时目录；不把桌面或 proxy 数据当作真实 FPS。

---

## 6. R2 实施结果（2026-11-15）

已实现：

- `vision/stream/window_capture.py`：窗口枚举、客户端区域抓取、前台/最小化/尺寸 fail-closed；
- `tools/capture_fps_pilot.py`：H/B-only、显式 POV/source/attestation、生命周期；
- `tools/check_fps_pilot.py`：视频解码/分辨率/哈希/生命周期/独立状态；
- `tools/run_cv_agent_offline.py`：H/B 视频上的 CV Agent dry-run 关联；
- `tests/test_fps_pilot.py`：协议、窗口状态、损坏视频、SHA、离线元数据测试。

已验证：

- 无窗口时 capture fail-closed；
- 中文标题 CS2（`反恐精英：全球攻势`）按 `cs2.exe` 进程识别成功；
- 真实 CS2 窗口单帧抓取通过（1920x1080）；
- `--focus-window` 可把 CS2 切到前台；终端失去焦点后仍能继续采集；
- 合成 2 帧视频上的 C 离线 dry-run 集成（`source_session_id`、视频 SHA、`dry_run=true`、`real_control=false`）；
- 真实 H/B C dry-run：3×3 tiling 后 H 759/1604、B 1124/1641 帧有检测，
  明显高于全分辨率直接推理的 43/1604、150/1641。

未实现/未验证：

- 真实 H/B 多帧 session；
- C 在真实 H/B 视频上的推理；
- Game Bot 自动启动；
- Agent 与采集的自动 start/stop 同步。

## 7. 结论

现有实现已从“中心 ROI 桌面录屏”升级为“指定窗口 + fail-closed + 生命周期 + 独立校验状态 + 离线 CV dry-run 入口”。

但仍**不能保证真实 CS2 第一人称采集通过**，因为当前没有 CS2 窗口/真人数据；C 实验也必须在 H/B 校验通过后才能执行。