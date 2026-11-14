# 多目标数据采集与标注任务书 v1

> 版本：v1.0（2026-11-14）  
> 目标：补充多目标场景数据，修正当前模型“2–4 个头只检出 0–2 个”的问题。  
> 当前阶段只做**采集 + 标注 + 质量检查**；不重训、不调 test、不改真实控制链路。

---

## 0. 目标与产出

产出目录：

```text
runs/pilot_20261115_multitarget/
├── captures/
│   ├── <session_static>/
│   ├── <session_slow>/
│   └── <session_fast>/
├── reports/
│   └── <session_id>.check.json
├── replays/
│   └── <session_id>.mp4
├── annotation_multitarget/
│   ├── images/          # 150 帧
│   ├── labels/          # 150 个 YOLO txt
│   ├── manifest.json
│   ├── data.yaml
│   ├── label_config.xml
│   └── check.json
└── NOTES.md
```

验收目标：

| 项目 | 目标 |
|---|---:|
| 新 session | 3 个（static / slow / fast 各 1 个） |
| 每个 session | 约 10 分钟 |
| 标注帧 | ≥150 |
| 含 2+ head 的帧 | ≥60 |
| 空图 | ≥20 |
| 90 帧 pilot test | 保持不动，不参与训练/调参 |

> 3 个 session 是底线。若时间允许，建议每个场景采 **2 个 5 分钟 session**，共 6 个，后续做 session-level train/val 会更稳。

---

## 1. 开始前准备

### 1.1 环境固定

沿用 pilot 的几何和设置：

- 桌面：2560×1440；
- CS2：居中的 1920×1080 窗口；
- ROI：320；
- 模型：`runs\detect\cs2_detection_v2\weights\best.onnx`；
- `conf=0.35`、`fps=30`、`head-only`；
- 同一地图、同一 bot 行为、同一 DPI/灵敏度/FOV；
- 不在一个 session 里切换场景或改参数。

### 1.2 安全与工具检查

新开 PowerShell：

```powershell
$PY = "D:\AI_Security\ai-game-security\.venv\Scripts\python.exe"
$DATA = "D:\AI_Security\ai-game-security\runs\pilot_20261115_multitarget"

& $PY -c "from vision.stream.safety import GlobalHotkeyKillSwitch; k=GlobalHotkeyKillSwitch(); k.start(); print('available=', k.available, 'is_running=', k.is_running); k.stop()"
```

必须看到：

```text
available= True is_running= True
```

如果降级为 `GetAsyncKeyState` 轮询，先实际按一次 ESC 和 F12；`is_running=False` 就停止，不要用 `--no-hotkeys` 绕过。

### 1.3 建立目录

```powershell
New-Item -ItemType Directory -Force `
  "$DATA\captures", "$DATA\reports", "$DATA\replays" | Out-Null
```

### 1.4 多目标场景设计

每个 session 尽量让画面里同时出现 **2–4 个 bot 头部**：

| scene | 摆位/行为 | 目的 |
|---|---|---|
| `static_target` | 2–4 个 bot 站在不同距离、不同水平位置，轻微晃动 | 静态多目标、不同尺度 |
| `slow_strafe` | 2–3 个 bot 慢速横移，保持同时可见 | 慢速多目标、遮挡变化 |
| `fast_strafe` | 2–3 个 bot 快速横移/急停 | 快速多目标、运动模糊 |

操作建议：

- 不要把 2 个 bot 完全重叠在一起；左右分开，保证标注时能区分。
- 至少让一组是“一个近、一个远”，覆盖不同 head 尺寸。
- 不要切到真实对局；继续用受控地图/bot。
- 如果 bot 被打掉，暂停/重开，不要用同一帧重复采样。

---

## 2. 采集 3 个 session

### 2.1 为什么用 dry-run 采集

本轮目标是**感知数据**，不是验证鼠标控制。建议用 `realtime_loop` 的 dry-run：

- 不加 `--apply-mouse`，不发送真实鼠标；
- 画面稳定，2–4 个目标不会因为自动吸附而快速丢失；
- 仍然记录 detection/selected/CSV 和视频；
- 不影响后续真实链路，真实控制仍由 `run_real.py` 验证。

如果你确实想采“自动吸附运动中的多目标”，可以把下文的 `-m vision.stream.realtime_loop` 换成 `run_real.py`，并在 notes 写 `control=real`。**同一批数据不要混两种模式。**

### 2.2 static 场景命令

```powershell
& $PY -m vision.stream.realtime_loop `
  --weights "runs\detect\cs2_detection_v2\weights\best.onnx" `
  --conf 0.35 --roi 320 --fps 30 --head-only `
  --no-overlay --frames 18000 `
  --record-dir "$DATA\captures" --record-fps 30 --record-scene static_target `
  --record-notes "multi_target=2-4; mode=dry_run; map=...; bot=...; desktop=2560x1440; window=1920x1080; dpi=...; sensitivity=...; fov=..."
```

操作：

1. 启动命令，等 3 秒稳定；
2. 保持 2–4 个 bot 同时可见，计时约 10 分钟；
3. 到时间按 **F12**，不要直接关终端；
4. 等 `Recording closed` / 进程退出；
5. 记录 session 路径和实际可见目标数。

### 2.3 slow / fast 场景

三个 session 分别执行，不要合并。先做 slow，检查通过后再做 fast。

#### slow_strafe（约 10 分钟）

```powershell
& $PY -m vision.stream.realtime_loop `
  --weights "runs\detect\cs2_detection_v2\weights\best.onnx" `
  --conf 0.35 --roi 320 --fps 30 --head-only `
  --no-overlay --frames 18000 `
  --record-dir "$DATA\captures" --record-fps 30 --record-scene slow_strafe `
  --record-notes "multi_target=2-3; mode=dry_run; map=...; bot=...; desktop=2560x1440; window=1920x1080; dpi=...; sensitivity=...; fov=..."
```

操作：让 2–3 个 bot 慢速横移并尽量同时可见；约 10 分钟或 `--frames 18000` 结束后按 F12。

#### fast_strafe（约 10 分钟）

```powershell
& $PY -m vision.stream.realtime_loop `
  --weights "runs\detect\cs2_detection_v2\weights\best.onnx" `
  --conf 0.35 --roi 320 --fps 30 --head-only `
  --no-overlay --frames 18000 `
  --record-dir "$DATA\captures" --record-fps 30 --record-scene fast_strafe `
  --record-notes "multi_target=2-3; mode=dry_run; map=...; bot=...; desktop=2560x1440; window=1920x1080; dpi=...; sensitivity=...; fov=..."
```

操作：让 2–3 个 bot 快速横移/急停，保持头部在画面内；约 10 分钟或 `--frames 18000` 结束后按 F12。

> 两条命令都要单独启动、单独检查；不要同时开两个采集进程。

### 2.4 每个 session 立即检查

```powershell
$session = (Get-ChildItem "$DATA\captures" -Directory | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
$id = Split-Path $session -Leaf

& $PY tools\check_session.py $session --verify-hash |
  Tee-Object -FilePath "$DATA\reports\$id.check.json"

& $PY tools\replay_session.py $session --output "$DATA\replays\$id.mp4"
```

单 session 通过标准：

- `"ok": true`，无 errors；
- `status=closed`、`record_mode=video`、`video_fps=30`；
- `frames_recorded >= 15000`（10 分钟目标；实际约 25–30fps）；
- `frames_skipped` 很小，`timestamp_monotonic=true`；
- `selected_frames > 0`；
- `capture.mp4` 可解码，回放中能看到检测框/时间戳；
- 人工抽查 0%、25%、50%、75%、100% 五个位置，确认画面里有 2+ 目标可见。

> dry-run session 的 `applied_mouse=false` 是正常的；不要拿它当失败。

---

## 3. 抽样 150 帧

三个 session 都通过后运行：

```powershell
& $PY tools\sample_multitarget_annotation.py `
  --pilot-root "$DATA" `
  --output "$DATA\annotation_multitarget" `
  --per-scene 50 `
  --multi-per-scene 20 `
  --single-per-scene 20 `
  --empty-per-scene 10
```

它会：

- 每个 scene 取最新 session；
- 每 scene 50 帧，共 **150 帧**；
- 优先取模型看到 2+ head 的帧（每 scene 20 帧，共 60 帧）；
- 保留 20 帧单头、10 帧空图/场景；
- 生成 `images/`、空 `labels/`、`manifest.json`、`data.yaml`、`README.md`。

看输出：

```json
{
  "counts": {
    "frames": 150,
    "model_multi_frames": 60,
    "model_empty_frames": 30
  }
}
```

注意：

- `model_multi_frames` 只是模型看到的数量，不是标注后的真实多目标数；
- 如果 `model_multi_frames` 明显低于 60，说明场景里目标不够多，或模型漏得太厉害；先补采，不要降低标准；
- 抽样完成后不要移动/重命名 `images/`。

---

## 4. 标注

### 4.1 配置 Label Studio

沿用 pilot 的配置：

```powershell
Copy-Item `
  "runs\pilot_20261114_1920x1080\annotation\label_config.xml" `
  "$DATA\annotation_multitarget\label_config.xml"
```

启动 Label Studio（1.23 不要用 `--version`）：

```powershell
label-studio start --port 8081
```

新建项目：

1. Labeling Setup 选 **Code**；
2. 粘贴 `label_config.xml` 内容；
3. 保存；
4. 导入 `annotation_multitarget/images/` 下 150 张图；
5. 开始标注。

完整 UI 流程和常见问题见 [`runs/pilot_20261114_1920x1080/annotation/README.md`](../runs/pilot_20261114_1920x1080/annotation/README.md)。

### 4.2 标注规则

- `enemy_head` → `0`
- `enemy_body` → `1`
- 每张图标注**所有可见目标**，包括模型没选中的；
- 一帧有 2 个可见 head，必须有 2 个 head 框；
- 紧凑框，不标 HUD/准星/队友；
- 不看 `model_detections` 抄框；它只是参考；
- 空图必须点 **Submit**，不要点 **Skip**；
- 不确定是否算可见时，按“能推断头部范围”标注，并在 notes 记录。

### 4.3 导出并转换

Label Studio 导出 JSON，保存为：

```text
$DATA\annotation_multitarget\labelstudio_export.json
```

转换：

```powershell
& $PY tools\labelstudio_to_yolo.py `
  --export "$DATA\annotation_multitarget\labelstudio_export.json" `
  --images-dir "$DATA\annotation_multitarget\images" `
  --labels-dir "$DATA\annotation_multitarget\labels"
```

通过标准：

```json
{
  "ok": true,
  "images": 150,
  "labeled_tasks": 150,
  "missing": [],
  "empty_labels": 30,
  "errors": []
}
```

`empty_labels` 不必刚好 30，但空图必须全部出现在导出里；`missing` 必须为空。

---

## 5. 标注质量检查

```powershell
& $PY tools\check_multitarget_annotation.py `
  --annotation "$DATA\annotation_multitarget" `
  --output "$DATA\annotation_multitarget\check.json"
```

通过标准：

```json
{
  "ok": true,
  "frames": 150,
  "multi_target_frames": 60,
  "empty_frames": 20
}
```

只看三项：

- `frames >= 150`；
- `multi_target_frames >= 60`：**按人工标签统计**，不是模型检测；
- `empty_frames >= 20`。

如果 `multi_target_frames` 不足：

- 不要改标签凑数；
- 补采多目标 session，或从现有新 captures 再抽；
- 重新抽样时用新目录，不要覆盖已标注数据。

---

## 6. 切分与交接

标注检查通过后，先不要训练。把以下文件交回：

```text
$DATA\annotation_multitarget\manifest.json
$DATA\annotation_multitarget\check.json
$DATA\annotation_multitarget\labels\
$DATA\reports\*.check.json
$DATA\NOTES.md
```

切分原则：

- 按 **session** 切，不按帧随机切；
- 90 帧 pilot test 永远不参与训练/调参；
- 新数据至少 2 个 session 做 train，1 个做 val；如果只有 3 个 session，val 的场景覆盖会有限，报告里要写明；
- 如果补到 6 个 session，优先 4 train / 2 val。

由 Agent 生成固定切分和数据卡，再决定是否微调。

---

## 7. 验收清单

### 7.1 采集

- [ ] 3 个新 session：static / slow / fast
- [ ] 每个约 10 分钟
- [ ] 每个 `check_session` `ok=true`
- [ ] 每个 replay 可解码
- [ ] 人工抽查确认有 2+ 目标同时可见
- [ ] `NOTES.md` 写清 map/bot/分辨率/DPI/灵敏度/FOV/实际目标数

### 7.2 抽样

- [ ] 150 帧
- [ ] 3 个 scene 各 50
- [ ] ≥60 帧模型看到 2+ head
- [ ] ≥20 帧空图
- [ ] 目录不覆盖旧数据

### 7.3 标注

- [ ] 150/150 个 task 都有 annotation（空图 Submit）
- [ ] 转换 `ok=true`、`missing=[]`
- [ ] 每个可见 head/body 都标了
- [ ] 多目标帧的 head 数正确
- [ ] `check_multitarget_annotation.py` `ok=true`
- [ ] `multi_target_frames >= 60`、`empty_frames >= 20`

### 7.4 边界

- [ ] 90 帧 pilot test 未加入训练
- [ ] 没有用 test 调 `conf` / `imgsz`
- [ ] 没有把 `clear_miss` 改回 `other`
- [ ] 没有重复帧凑数
- [ ] 没有改真实控制链路

---

## 8. 时间预算

| 阶段 | 预计 |
|---|---:|
| 3 × 10 分钟采集 + 检查 | 45–60 分钟 |
| 抽样 + 配置 Label Studio | 15–20 分钟 |
| 150 帧标注 | 2–4 小时（取决于目标数） |
| 转换 + 质量检查 | 15 分钟 |

---

## 9. 现在开始

按顺序执行：

1. 设置 `$PY` / `$DATA`；
2. 跑安全热键检查；
3. 采 `static_target`，检查；
4. 采 `slow_strafe`，检查；
5. 采 `fast_strafe`，检查；
6. 抽样 150 帧；
7. Label Studio 标注；
8. 转换 + `check_multitarget_annotation.py`；
9. 把 `check.json`、`manifest.json` 交回。

如果任何一步 `ok=false`，停下来修，不要用降低标准的方式绕过。