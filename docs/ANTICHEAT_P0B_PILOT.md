# P0-B Pilot：第一人称 POV 采集与离线 CV dry-run

版本：v2（R2 升级）  
日期：2026-11-15  
状态：**工具实现完成；真实 H/B 采集仍待桌面环境；C 依赖已校验 H/B 视频**  
关联：

- [`ANTICHEAT_LABEL_PROTOCOL.md`](ANTICHEAT_LABEL_PROTOCOL.md)
- [`ANTICHEAT_P0B_CAPTURE_REVIEW.md`](ANTICHEAT_P0B_CAPTURE_REVIEW.md)
- [`ANTICHEAT_P0B_AGENT_READINESS.md`](ANTICHEAT_P0B_AGENT_READINESS.md)

---

## 1. 本轮变更

取消第三人称/自由视角正式采集。只允许：

```text
H: human    + player_pov
B: game_bot + observer_followed_bot
C: 离线 dry-run，对已校验 H/B 视频做推理
```

采集工具现在：

- 只抓指定 CS2 窗口的**客户端区域**；
- 窗口不存在、最小化、失焦、尺寸变化时**直接失败**，不降级为桌面；
- 要求显式 `--view-mode first_person`；
- 要求显式 `--capture-source`，不由 `agent_type` 推断；
- 要求人工 `--attest-pov` 和 `--attest-experiment`；
- 写 `lifecycle.jsonl`；
- 不再允许 `cv_agent` 作为实时采集标签。

---

## 2. 当前环境状态

```text
CS2 进程/窗口        已发现（cs2.exe，中文标题，客户端 1920x1080）
H pilot              p0b_human_20261116_152512（60s，timebase 通过）
B pilot              p0b_game_bot_20261116_152746（60s，timebase 通过）
C 离线 dry-run       H/B 各完成一次，source/video/model SHA 已关联
检测覆盖（3×3 tiling） H: 759/1604 帧；B: 1124/1641 帧
```

因此本文件是操作手册和协议说明；H/B/C 的技术流程已跑通，
但**行为学结论仍不能成立**，需要先确认视频中目标可见性和覆盖度。

已完成的离线技术验证：

```text
窗口不存在 -> fail-closed
中文标题 CS2 -> 按 cs2.exe 识别成功
真实 CS2 单帧抓取 -> 1920x1080 通过
第三人称 -> 拒绝
缺少 attestation -> 拒绝
合成 2 帧视频 -> C 离线 dry-run 成功，source SHA/源 session 关联正确
真实 H/B session -> 未验证
```

---

## 3. 工具

### 3.1 窗口采集与 session

[`tools/capture_fps_pilot.py`](../tools/capture_fps_pilot.py)

[`vision/stream/window_capture.py`](../vision/stream/window_capture.py)

- Windows `EnumWindows` 默认按 **`cs2.exe` 进程**识别窗口，不依赖本地化标题；
  已验证中文标题 `反恐精英：全球攻势` 时仍可识别；
- 读取客户端区域；
- 每帧校验窗口仍存在、可见、未最小化、前台、尺寸未变；
- 使用 `mss` 抓取客户端区域；
- 默认 `--fps 30`；1920×1080 mss 抓屏在 60fps 下实测约 26–29fps，
  会触发 `TIMEBASE_CONSISTENT=false`；
- 默认 `--focus-window` 会把 CS2 切到前台；运行后**不要点回终端**，
  否则游戏失焦会触发 fail-closed；
- 不抓桌面中心 ROI，不使用 `PrintWindow`，不注入游戏。

限制：

- 独占全屏/HDR/受保护内容可能失败；
- 窗口被其他窗口遮挡或失焦时会拒绝采集；
- 需要实际窗口和可捕获的桌面合成画面。

### 3.2 校验

[`tools/check_fps_pilot.py`](../tools/check_fps_pilot.py)

独立状态：

```text
FILE_INTEGRITY_VERIFIED
VIDEO_DECODE_VERIFIED
GAME_WINDOW_OBSERVED
POV_MANUALLY_ATTESTED
EXPERIMENT_MANUALLY_ATTESTED
TIMEBASE_CONSISTENT
```

`--verify-hash` 只证明文件哈希；不证明 Agent 身份或人工流程。

### 3.3 离线 CV dry-run

[`tools/run_cv_agent_offline.py`](../tools/run_cv_agent_offline.py)

- 输入：已通过 `check_fps_pilot --verify-hash` 的 H/B session；
- 读取 `capture.mp4`；
- 使用 `TiledDetector`（默认 3×3、tile 720）把全分辨率 POV 切成与训练 ROI
  更接近的块，再合并检测；这是为解决 320 ROI 模型直接跑 1920×1080 时
  小目标漏检；
- 复用 `TiledDetector -> AimPipeline -> CSVLoggerBackend`；
- 强制 `apply_mouse=False`；
- 不启动 `run_real.py`，不发送输入；
- 输出：
  - `inference_frames.jsonl`
  - `control_moves.csv`
  - `inference_meta.json`
  - `inference_manifest.json`

---

## 4. H：Human POV

### 4.1 操作步骤

1. 启动 CS2 离线地图；不连接正式服务器。
2. 人工确认当前是**第一人称玩家视角**。
3. 保持 CS2 窗口可见、前台、未最小化。
4. 运行采集：

```powershell
.\.venv\Scripts\python.exe tools\capture_fps_pilot.py `
  --agent-type human `
  --capture-source player_pov `
  --view-mode first_person `
  --scene static_target `
  --map-name aim_botz `
  --weapon ak47 `
  --sensitivity 0.8 `
  --fov 90 `
  --duration 180 `
  --operator-id anon_h01 `
  --output-dir runs\captures\p0b_pilot `
  --attest-pov `
  --attest-experiment `
  --confirm-offline
```

5. 工具默认会把 CS2 切到前台；终端会失去焦点，这是正常的。
6. 在 2–5 分钟内正常操作；不要切到桌面、终端或其他窗口。
7. 按 Ctrl+C 或等待 duration 结束。
8. 校验：

```powershell
# 自动取最新 session，避免把 <session-id> 原样复制
$session = Get-ChildItem runs\captures\p0b_pilot -Directory |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
.\.venv\Scripts\python.exe tools\check_fps_pilot.py $session.FullName --verify-hash
```

8. 人工抽查画面、POV 和 session 时间线。

> **时间基注意：** 如果 `check_fps_pilot` 报
> `video duration ... differs from session duration ...`，说明实际抓屏帧率低于
> 请求 fps，视频会比真实 session 短；`TIMEBASE_CONSISTENT=false`，该 session
> 不能用于行为时序结论。应使用默认 30 fps 或更低的 `--fps` 重录，或后续改用
> events 时间戳关联视频。

### 4.2 参与者

- `--operator-id` 是匿名标签，不是身份认证；
- 不采集姓名、账号、聊天、语音；
- 需要成年人知情同意；
- 同一参与者/设备应使用稳定匿名 ID，便于分组切分。

---

## 5. B：Game Bot POV

前提：项目没有自研 CS2 Game Bot。必须使用 **CS2 内置 Bot** 和观察者模式。

### 5.1 操作步骤

1. 启动 CS2 离线地图；
2. 创建/启动 CS2 内置 Bot；
3. 进入观察者模式；
4. 选择目标 Bot；
5. 切换到该 Bot 的**第一人称视角**；
6. 人工确认不是第三人称/自由视角；
7. 保持 CS2 前台、可见；
8. 运行：

```powershell
.\.venv\Scripts\python.exe tools\capture_fps_pilot.py `
  --agent-type game_bot `
  --capture-source observer_followed_bot `
  --view-mode first_person `
  --scene static_target `
  --map-name aim_botz `
  --weapon ak47 `
  --sensitivity 0.8 `
  --fov 90 `
  --duration 180 `
  --operator-id anon_b01 `
  --output-dir runs\captures\p0b_pilot `
  --attest-pov `
  --attest-experiment `
  --confirm-offline
```

9. 校验同上。

### 5.2 失败条件

如果无法稳定跟随 Bot 第一人称视角：

- **停止该 session**；
- 记录原因；
- 不自动降级为第三人称；
- 不把观察者自由视角标记为 `observer_followed_bot`。

---

## 6. C：CV Agent 离线 dry-run

C 不再实时采集，而是对已校验的 H/B 视频做离线推理。

### 6.1 前提

源 session 必须：

- `agent_type` 为 `human` 或 `game_bot`；
- `view_mode=first_person`；
- `capture_source` 匹配；
- `check_fps_pilot --verify-hash` 返回 `ok=true`；
- 原始视频存在且可解码。

### 6.2 命令

```powershell
.\.venv\Scripts\python.exe tools\run_cv_agent_offline.py `
  "runs\captures\p0b_pilot\<verified-session>" `
  --output-dir runs\eval\anticheat_cv_offline\<source-session> `
  --model runs\detect\cs2_detection_v2\weights\best.onnx `
  --conf 0.35 `
  --iou 0.5
```

### 6.3 输出

```text
inference_frames.jsonl      逐帧检测/选择/轨迹/特征；dry_run=true
control_moves.csv           CSV 控制日志（log-only，无真实输出）
inference_meta.json         source session、视频 SHA256、模型 SHA256、tiling 配置
inference_manifest.json     输出文件哈希
```

实际 pilot（使用 **new** 模型 + 3×3 tiling）：

```text
H  759 / 1604 帧有检测，671 帧选中，671 行 CSV
B 1124 / 1641 帧有检测，908 帧选中，908 行 CSV
```

2026-11-16 后默认模型已回退 old；上述数字仅对应 new 模型对比，不能作为
old 默认下的结果。

未 tiling 的同一份 H/B 视频只有 43/1604、150/1641 帧有检测，说明
全分辨率直接推理会因目标尺度过小而严重漏检。

`--model` 默认也是旧 `cs2_detection_v2`；如需复现 new-model 对比，显式传
`runs\detect\cs2_multitarget_ft_v1\weights\best.onnx`。

### 6.4 安全边界

- 没有 `--apply-mouse`；
- 不启动 `run_real.py`；
- 不发送游戏输入；
- 不修改源视频；
- 所有逐帧记录标记 `dry_run=true`、`real_control=false`。

---

## 7. 生命周期

`lifecycle.jsonl` 依次记录：

```text
session_created
game_window_verified
capture_started
experiment_started
experiment_finished
capture_stopped
manifest_generated
video_artifact
integrity_verified
```

异常时记录：

```text
capture_aborted
```

每条事件包含：

- UTC 墙上时间；
- `time.perf_counter_ns()` 单调时间；
- 必要字段（窗口、视频哈希、错误原因等）。

无法获得的事件不伪造。

---

## 8. 校验状态

```text
FILE_INTEGRITY_VERIFIED    --verify-hash 通过
VIDEO_DECODE_VERIFIED      视频可解码、分辨率/时长合理
GAME_WINDOW_OBSERVED       有窗口元数据且生命周期记录
POV_MANUALLY_ATTESTED      人工 --attest-pov
EXPERIMENT_MANUALLY_ATTESTED 人工 --attest-experiment
TIMEBASE_CONSISTENT        视频时长与 session 时长在 20% 容差内
```

这些状态不可互相替代。`check_fps_pilot` 返回 `ok=true` 需要全部满足。

---

## 9. 当前不能做的事

- 无 CS2/窗口时自动录桌面；
- 自动启动/控制 Game Bot；
- 自动启动/控制 CV Agent；
- 把第三人称/自由视角标记为 Bot POV；
- 把 proxy/合成轨迹当作真实 H/B；
- 在 C 推理中发送真实输入；
- 用文件哈希代替人工 POV/实验确认。

---

## 10. 下一步

1. 在真实离线桌面运行 H 和 B 各 1 个 pilot session；
2. 用 `check_fps_pilot --verify-hash` 校验；
3. 抽查 POV、目标可见性、时间线；
4. 通过后运行 C 离线 dry-run；
5. 确认 `inference_meta.json` 的 source session/video SHA256 对应；
6. 之后才考虑扩大 H/B 到每类 ≥20 sessions。