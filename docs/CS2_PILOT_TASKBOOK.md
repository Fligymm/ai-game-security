# CS2 受控采集任务书 v0

> 版本：v0.2（2026-11-14）  
> 执行人：项目所有者  
> 目的：在不改动现有 CS2 自动吸附链路的前提下，完成 1 次 dry-run smoke、1 次真实 smoke、3 个场景各 10 分钟的 pilot 采集，并产出可校验的 manifest/质量报告/回放。  
> 当前状态：**Pilot v0 已完成**。实际数据在 `runs/pilot_20261114_1920x1080`，90 帧标注和 ONNX 基线也已完成。本文件保留为采集/验收规范；下一阶段见 [`docs/PERCEPTION_TASKBOOK.md`](PERCEPTION_TASKBOOK.md)。  
> 说明：下文路径中的 `runs/pilot_20261114` 是原始模板；实际执行请统一使用 `runs/pilot_20261114_1920x1080`。

---

## 1. 这次要交付什么

完成后你应得到：

```text
runs/pilot_20261114/
├── captures/
│   ├── realtime_cs2_agent_YYYYmmdd_HHMMSS/   # smoke_dry
│   ├── realtime_cs2_agent_YYYYmmdd_HHMMSS/   # smoke_real
│   ├── realtime_cs2_agent_YYYYmmdd_HHMMSS/   # static_target
│   ├── realtime_cs2_agent_YYYYmmdd_HHMMSS/   # slow_strafe
│   └── realtime_cs2_agent_YYYYmmdd_HHMMSS/   # fast_strafe
├── reports/
│   ├── <session_id>.check.json
│   └── ...
├── replays/
│   ├── <session_id>.mp4
│   └── ...
└── NOTES.md
```

每个 capture 目录内由工具自动生成：

- `session.json`
- `events.jsonl`
- `capture.mp4`（默认）
- `manifest.json`

不要手动修改这些文件；如采集异常，保留现场并重跑。

---

## 2. 执行前准备

### 2.1 环境

- Windows 交互桌面（不是远程服务/无桌面会话）。
- 受控 CS2：离线/私人/Workshop 环境，不进入联网竞技。
- 现有权重：`runs\detect\cs2_detection_v2\weights\best.onnx`。
- Python：`.\.venv\Scripts\python.exe`。
- 磁盘：至少预留 2 GB（3 个 10 分钟 320×320/30fps 视频足够）。
- 关闭会占用 ESC/F12 的程序（录屏、宏、部分 overlay）。

先确认用的是项目虚拟环境，而不是系统 Python：

```powershell
$PY = ".\.venv\Scripts\python.exe"
& $PY -c "import sys; print(sys.executable)"
```

输出应指向 `D:\AI_Security\ai-game-security\.venv\Scripts\python.exe`。如果出现 `C:\Python\...`，先修正 `$PY`。

> PowerShell 新开窗口不会继承旧变量；每条命令前确认 `$PY`/`$PILOT` 有值。最稳妥是使用绝对路径：
> ```powershell
> $PY = "D:\AI_Security\ai-game-security\.venv\Scripts\python.exe"
> $PILOT = "D:\AI_Security\ai-game-security\runs\pilot_20261114"
> ```

### 2.2 固定参数（3 个 pilot 必须一致）

| 参数 | 值 |
|---|---|
| 权重 | `runs\detect\cs2_detection_v2\weights\best.onnx` |
| `--conf` | `0.35` |
| `--roi` | `320` |
| `--fps` | `30` |
| `--head-only` | 开启 |
| `--max-mouse-step` | `16` |
| `--mouse-deadzone` | `1.0` |
| `--output-confirm-frames` | `3` |
| `--record-fps` | `30` |
| `--record-mode` | `video` |
| `--record-source` | 默认 `realtime_cs2_agent`（不要改成 human） |

环境（地图、分辨率、DPI、灵敏度、FOV、bot 行为）也必须固定；把值写进 `--record-notes`。

### 2.3 安全前置检查（必须）

```powershell
$PY = ".\.venv\Scripts\python.exe"
& $PY -c "from vision.stream.safety import GlobalHotkeyKillSwitch; k=GlobalHotkeyKillSwitch(); k.start(); print('available=', k.available, 'is_running=', k.is_running); k.stop()"
```

**通过标准**：输出 `available= True is_running= True`。

如果 `RegisterHotKey` 被其他程序占用，当前版本会自动降级为 `GetAsyncKeyState` 轮询，并打印：

```text
[WARNING] global hotkey registration failed; using GetAsyncKeyState polling for ESC/F12
```

只要随后仍是 `is_running= True`，可以继续；但必须实际按一次 ESC 和 F12 验证轮询路径有效。若 `is_running=False`：

1. 不要继续真实控制；
2. 检查 ESC/F12 是否被其他程序占用；
3. 换到交互桌面/重启终端后重试；
4. 仍失败就停止并报告，**不要**用 `--no-hotkeys` 绕过。

> 自动化/远程会话中该检查可能失败；这是 fail-closed 的预期行为，不代表实机链路坏了。

---

## 3. 阶段 A：dry-run smoke（不发送鼠标）

### 3.1 命令

```powershell
$PY = ".\.venv\Scripts\python.exe"
$PILOT = "runs\pilot_20261114"
New-Item -ItemType Directory -Force "$PILOT\captures", "$PILOT\reports", "$PILOT\replays" | Out-Null

& $PY -m vision.stream.realtime_loop `
  --weights "runs\detect\cs2_detection_v2\weights\best.onnx" `
  --conf 0.35 --roi 320 --fps 30 --head-only --frames 300 --preview `
  --record-dir "$PILOT\captures" --record-fps 30 --record-scene smoke_dry `
  --record-notes "smoke_dry; no mouse; map=...; resolution=...; dpi=...; sensitivity=...; fov=..."
```

说明：

- 不加 `--apply-mouse`，只记录 CSV/采集，不发送真实鼠标。
- `--frames 300` 约 10 秒，自动结束。
- 结束后记下最后打印的 session 路径。

### 3.2 检查

```powershell
$session = (Get-ChildItem "$PILOT\captures" -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
$id = Split-Path $session -Leaf
& $PY tools\check_session.py $session --verify-hash | Tee-Object -FilePath "$PILOT\reports\$id.check.json"
& $PY tools\replay_session.py $session --output "$PILOT\replays\$id.mp4"
```

> `<session_id>` 只是文档占位符，不是可执行文件名。上面的 `$session` 会自动选最新 session；检查旧 session 时把 `$session` 改成实际路径。

**通过标准**：

- `check_session` 输出 `"ok": true`；无 errors；
- `session.json` 的 `record_mode=video`、`status=closed`；
- `frames_recorded > 0`，`frames_seen = frames_recorded + frames_skipped`；
- `timestamp_monotonic=true`；
- `capture.mp4` 能打开，回放中能看到检测框/时间戳；
- `applied_mouse` 可以为 false（dry-run 正常）。

修复后的 300 帧 smoke 预期：`frames_recorded≈300`、`frames_skipped=0`、`effective_fps≈25–30`。如果仍是 180 左右、`effective_fps≈15`，先不要继续。

如果 `check_session` 报 `effective_fps < 20`，说明录制采样在帧突发时丢了帧；当前代码已在 `video_fps >= target_fps` 时关闭抽样，直接用同一命令重跑即可，不要降低标准。

---

## 4. 阶段 B：真实 smoke（10–20 秒）

### 4.1 命令

```powershell
& $PY run_real.py `
  --weights "runs\detect\cs2_detection_v2\weights\best.onnx" `
  --conf 0.35 --roi 320 --fps 30 --head-only `
  --max-mouse-step 16 --mouse-deadzone 1.0 --output-confirm-frames 3 `
  --frames 300 --preview `
  --record-dir "$PILOT\captures" --record-fps 30 --record-scene smoke_real `
  --record-notes "smoke_real; map=...; resolution=...; dpi=...; sensitivity=...; fov=..."
```

`run_real.py` 会显式补 `--apply-mouse`，因此这是真实控制路径。只在受控 CS2 中执行。

### 4.2 检查

```powershell
$session = (Get-ChildItem "$PILOT\captures" -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
$id = Split-Path $session -Leaf
& $PY tools\check_session.py $session --verify-hash | Tee-Object -FilePath "$PILOT\reports\$id.check.json"
& $PY tools\replay_session.py $session --output "$PILOT\replays\$id.mp4"
```

**通过标准**：

- dry-run 的所有标准；
- `detections_total > 0`；
- `selected_frames > 0`；
- `applied_frames > 0`（否则说明真实后端/热键/目标选择没生效，停止排查）；
- F12 能在 1 秒内停止输出；ESC 能暂停。

---

## 5. 阶段 C：3 个场景 pilot（每个 10 分钟）

### 5.1 场景矩阵

| scene | 目标运动 | 时长 | 主要观察 |
|---|---|---|---|
| `static_target` | 静止或轻微晃动 | 10 min | 检测稳定性、小目标、误检 |
| `slow_strafe` | 慢速横移 | 10 min | 跟踪连续性、延迟 |
| `fast_strafe` | 快速横移/急停 | 10 min | 丢失、过冲、重捕获 |

每个 session 只做一个场景。不要在一个 session 中切换场景。

### 5.2 每个场景的命令模板

把 `<scene>` 替换为 `static_target` / `slow_strafe` / `fast_strafe`：

```powershell
& $PY run_real.py `
  --weights "runs\detect\cs2_detection_v2\weights\best.onnx" `
  --conf 0.35 --roi 320 --fps 30 --head-only `
  --max-mouse-step 16 --mouse-deadzone 1.0 --output-confirm-frames 3 `
  --no-overlay `
  --record-dir "$PILOT\captures" --record-fps 30 --record-scene <scene> `
  --record-notes "<scene>; map=...; bot=...; resolution=...; dpi=...; sensitivity=...; fov=..."
```

操作流程：

1. 启动命令，等待窗口/采集稳定 3 秒；
2. 开始计时 10 分钟；保持同一场景行为；
3. 结束时按 F12（不要直接关终端）；
4. 等 `Recording closed` / 进程退出；
5. 立刻运行检查与回放；
6. 填写 `NOTES.md` 中该 session 一行。

> `--no-overlay` 用于减少采集开销；如果看不到画面，可先用 `--preview` 跑 30 秒确认设置，再按正式命令重跑 10 分钟。正式 3 个 session 必须使用同一参数。

### 5.3 每个 session 的检查

```powershell
$session = (Get-ChildItem "$PILOT\captures" -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
$id = Split-Path $session -Leaf
& $PY tools\check_session.py $session --verify-hash | Tee-Object -FilePath "$PILOT\reports\$id.check.json"
& $PY tools\replay_session.py $session --output "$PILOT\replays\$id.mp4"
```

人工抽查回放中 0%、25%、50%、75%、100% 五个位置，确认：

- 检测框存在且大致贴合目标；
- 选中框（红色）与检测框一致；
- 时间戳/帧号在变化；
- 画面没有大面积黑屏/卡死/重复帧。

---

## 6. 验收标准

### 6.1 单 session 必须满足

| ID | 标准 | 判定 |
|---|---|---|
| P-01 | `check_session` 的 `"ok": true` | 必须 |
| P-02 | `status=closed` | 必须 |
| P-03 | `record_mode=video`、`video_fps=30` | 必须 |
| P-04 | `frames_seen == frames_recorded + frames_skipped` | 必须 |
| P-05 | `timestamp_monotonic=true`，`non_monotonic_timestamps=0` | 必须 |
| P-06 | `duration_s` 在 540–660 秒（目标 600 秒，±10%，手动 F12 容差） | 必须 |
| P-07 | `effective_fps >= 20` | 必须 |
| P-08 | `frames_recorded > 0`、`capture.mp4` 可解码 | 必须 |
| P-09 | `manifest.json` 文件存在、sha256 校验通过 | 必须 |
| P-10 | `detections_total > 0` | 必须 |
| P-11 | `selected_frames > 0` | 必须 |
| P-12 | 真实 session 的 `applied_frames > 0` | 必须 |
| P-13 | 回放视频能生成并可打开 | 必须 |
| P-14 | 同一 session 内环境/参数未变化 | 必须 |

> P-06 的窗口是 9–11 分钟（540–660 秒），目标仍是 10 分钟；不要为了凑秒数故意暂停或剪断场景。低于 540 秒需要重跑。

### 6.2 三个 pilot 整体必须满足

| ID | 标准 | 判定 |
|---|---|---|
| D-01 | 3 个不同 scene，且标签与内容一致 | 必须 |
| D-02 | 每个 session 满足 P-01～P-14 | 必须 |
| D-03 | 3 个 session 使用同一权重/conf/ROI/FPS/灵敏度/分辨率/DPI/FOV | 必须 |
| D-04 | 3 个 session 总有效时长 ≥ 29 分钟（约 30 分钟） | 必须 |
| D-05 | 每个 session 都有 check.json 和 replay mp4 | 必须 |
| D-06 | `NOTES.md` 记录环境、异常、重跑原因 | 必须 |

### 6.3 建议但不必失败的标准

- `static_target` 的 `selected_frames / frames_recorded >= 0.5`；低于此值记录为“检测/选择异常”，不要删数据。
- `slow_strafe` / `fast_strafe` 的选中率只记录，不设硬阈值；重点看丢失与重捕获。
- 检测框人工抽查：每 session 至少 5 个时间点；发现明显漏检/错框写进 `NOTES.md`。

---

## 7. 失败与重跑规则

出现以下任一情况，**停止并重跑该 session**，不要删旧目录：

| 现象 | 处理 |
|---|---|
| 热键检查 `is_running=False` | 停止；修好热键/换交互桌面；不要用 `--no-hotkeys` |
| `check_session` 有 errors | 保留现场；记录错误；修复后重跑 |
| `status` 不是 `closed`（崩溃/强杀） | 标记 invalid；重跑 |
| `applied_frames=0`（真实 session） | 检查 Win32 hook/热键/后端；重跑 |
| `detections_total=0` | 检查权重/类别映射；重跑 |
| `effective_fps < 20` | 关闭后台程序/录屏；重跑 |
| 视频无法解码 | 保留；先用 `--record-mode frames` 做 30 秒 smoke 排查 |
| 中途换了地图/分辨率/灵敏度 | 当前 session invalid；恢复固定环境后重跑 |

重跑时用新的时间戳目录，不要覆盖旧 session。

---

## 8. 需要提交/保留的证据

完成后保留整个 `runs\pilot_20261114`，并确认：

- 3 个 pilot session 目录（加 2 个 smoke 目录）；
- 每个 session 的 `reports\<session_id>.check.json`；
- 每个 session 的 `replays\<session_id>.mp4`；
- `NOTES.md`。

`NOTES.md` 建议格式：

```markdown
# CS2 Pilot Notes

## 环境
- CS2 版本/地图：
- 分辨率 / DPI 缩放：
- 显示模式（全屏/窗口）：
- 灵敏度 / FOV：
- bot/目标设置：
- GPU / 采集后端：

## Sessions

| session_id | scene | start | duration_s | effective_fps | frames_recorded | applied_frames | check | 备注 |
|---|---|---|---:|---:|---:|---:|---|---|
| ... | static_target | ... | ... | ... | ... | ... | ok | ... |

## 异常/重跑
- ...
```

---

## 9. 明确不要做的事

- 不要进入联网竞技/匹配；只做受控离线/私人环境。
- 不要在 pilot 期间改代码、换权重、换 conf/ROI/FPS/灵敏度。
- 不要用 `--no-hotkeys` 跑真实控制。
- 不要用 `--record-mode frames` 做 10 分钟长采集（文件太多）。
- 不要删除失败 session；保留现场用于分析。
- 不要手动编辑 `session.json`/`events.jsonl`/`manifest.json`。
- 不要用 `--record-source human_cs2` 标记自动吸附 session；当前 source 是 `realtime_cs2_agent`。

---

## 10. 时间预算与完成定义

| 阶段 | 预计 |
|---|---|
| 环境/热键检查 | 15 分钟 |
| dry smoke + 检查 | 10 分钟 |
| real smoke + 检查 | 10 分钟 |
| 3 × 10 分钟 pilot + 检查 | 45–60 分钟 |
| 汇总 NOTES | 10 分钟 |

**完成定义（DoD）**：

1. 热键检查通过；
2. dry smoke 与 real smoke 各 1 个，check 通过；
3. 3 个场景各 1 个 10 分钟 session，全部 check 通过；
4. 3 个 replay 生成并抽查；
5. `NOTES.md` 完整；
6. 没有用禁用参数，没有删除失败数据。

完成后把 `runs\pilot_20261114` 的路径发我；我基于这些真实 session 做 manifest 汇总、数据质量分析、固定切分和检测/追踪基线。