# 多模态采集数据契约 v0

> 状态：M1 草案，已由 `vision/stream/session_recorder.py` 实现  
> 适用：`RealtimeAimLoop` 的屏幕帧 + 感知结果 + 控制事件 + 元数据采集  
> 不适用：真实鼠标输入采集（后续 `human_cs2` 扩展）；行为反作弊标签

---

## 1. 目录结构

一次 capture 是一个独立目录：

```text
runs/captures/
└── realtime_cs2_agent_20261114_123000/
    ├── session.json          # 会话元数据 + 初始/结束状态
    ├── events.jsonl          # 每个被采样帧一行，含感知/控制事件
    ├── manifest.json         # 文件清单、sha256、数量、质量指标
    ├── capture.mp4           # mode=video（默认）
    └── frames/               # mode=frames
        ├── frame_000000.jpg
        └── frame_000001.jpg
```

`mode=video` 与 `mode=frames` 二选一。默认 video，适合长时间采集；frames 适合逐帧标注/质检。

---

## 2. `session.json`

```json
{
  "schema_version": "multimodal.session.v0",
  "status": "recording | closed",
  "session_id": "realtime_cs2_agent_20261114_123000",
  "source": "realtime_cs2_agent",
  "game": "cs2_offline",
  "scene": "static_target",
  "operator_id": "anonymous",
  "width": 640,
  "height": 640,
  "target_fps": 144,
  "roi": [960, 400, 640, 640],
  "backend": "bettercam",
  "notes": "M1 pilot",
  "git_commit": "",
  "record_mode": "video",
  "video_fps": 60,
  "jpeg_quality": 92,
  "started_at_ns": 123456789,
  "started_at_wall_ns": 1760000000000000000,
  "started_at_iso": "2026-11-14T12:30:00+00:00",
  "ended_at_ns": 123999999,
  "duration_s": 10.0,
  "frames_seen": 600,
  "frames_recorded": 300,
  "frames_skipped": 300,
  "events_path": "events.jsonl",
  "video_path": "capture.mp4",
  "frames_dir": null
}
```

字段说明：

- `source`：`realtime_cs2_agent` 表示现有自动瞄准闭环产生的控制事件，不是人类鼠标原始输入；后续人类采集使用 `human_cs2`。
- `timestamp_ns`/`started_at_ns`：`time.perf_counter_ns()` 单调时钟，用于跨帧/事件对齐。
- `started_at_wall_ns`/`started_at_iso`：墙钟，用于人工定位 session。
- `width/height`：ROI 输出尺寸，必须与实际帧一致。
- `roi`：`(left, top, right, bottom)` 绝对屏幕坐标；无法取得时为 `null`。
- `target_fps`：抓取器目标 FPS；`video_fps`：回放 FPS，且被钳制到 `target_fps`，避免视频比源快。
- `frames_seen`：进入 recorder 的帧数；`frames_recorded`：实际写入视频/图片的帧数；`frames_skipped`：`video_fps < target_fps` 时按采样间隔跳过的帧数。两者相等时不做抽样。

---

## 3. `events.jsonl`

每行一个 JSON 对象，对应一个实际写入的帧：

```json
{
  "schema_version": "multimodal.session.v0",
  "session_id": "realtime_cs2_agent_20261114_123000",
  "frame_id": 42,
  "record_index": 21,
  "timestamp_ns": 123456789,
  "wall_time_ns": 1760000000000000000,
  "detections": [
    {
      "x1": 310.0,
      "y1": 280.0,
      "x2": 330.0,
      "y2": 300.0,
      "confidence": 0.91,
      "class_id": 0,
      "track_id": 7
    }
  ],
  "selected": {
    "x1": 310.0,
    "y1": 280.0,
    "x2": 330.0,
    "y2": 300.0,
    "confidence": 0.91,
    "class_id": 0,
    "class_name": "enemy_head",
    "track_id": 7,
    "delta_x": 12.0,
    "delta_y": -8.0
  },
  "applied_mouse": false,
  "mouse_delta": [4.0, -3.0],
  "extra": {
    "processed_at_ns": 123456999,
    "prediction_enabled": true,
    "trajectory": {
      "name": "linear",
      "points": [[0.0, 0.0], [4.0, -2.0], [8.0, -4.0]]
    }
  }
}
```

关键点：

- `frame_id`：`RealtimeAimLoop.step()` 的原始帧序号，跳采样时仍保留，便于回溯。
- `record_index`：写入视频/图片序列的连续序号（从 0 开始）。
- `timestamp_ns`：该帧从抓取器返回时的单调时间；优先取 `ScreenGrabber.last_frame_timestamp_ns`。
- `processed_at_ns`：pipeline 处理完成时间；两者差值可用于处理延迟分析。
- `detections`：原始检测框，像素坐标；`track_id` 可为 `null`。
- `selected`：最终目标选择结果；无目标时为 `null`。
- `applied_mouse`：只有真实后端实际发送非零位移时为 `true`；CSV-only 永远 `false`。
- `mouse_delta`：本帧控制输出（未发送也记录计划值）；无目标时可 `null`。
- `extra.trajectory`：本帧计划轨迹，点为相对准星的偏移；无目标时为 `null`。回放工具会把它叠加为紫色折线。

---

## 4. `manifest.json`

```json
{
  "schema_version": "multimodal.manifest.v0",
  "session_id": "realtime_cs2_agent_20261114_123000",
  "session": { "...": "CaptureMetadata 的完整副本" },
  "counts": {
    "frames_seen": 600,
    "frames_recorded": 300,
    "frames_skipped": 300,
    "detections_total": 1234,
    "selected_frames": 250,
    "applied_frames": 0
  },
  "quality": {
    "duration_s": 10.0,
    "effective_fps": 30.0,
    "timestamp_monotonic": true,
    "non_monotonic_timestamps": 0
  },
  "files": [
    {
      "path": "events.jsonl",
      "bytes": 123456,
      "sha256": "..."
    }
  ]
}
```

`files` 包含 `session.json`、`events.jsonl`、`capture.mp4`（或所有 frame JPEG）的路径、大小、sha256。用于数据版本、复现和传输校验。

---

## 5. 质量规则（v0）

| 检查 | 规则 | 失败处理 |
|---|---|---|
| 帧尺寸 | 所有帧等于 `width × height` | 拒绝该帧并报错 |
| 时间戳 | `timestamp_ns` 非递减 | manifest 记录 `timestamp_monotonic=false` |
| 采样 | `recorded + skipped == seen` | 检查 session 计数 |
| 文件 | manifest 中每个文件存在且 hash 可复算 | 质量脚本失败 |
| 事件 | 每个 event 有 `frame_id/record_index/timestamp_ns` | 质量脚本失败 |
| 同步 | 事件时间与视频帧时间在采样间隔内 | 人工/脚本抽查 |

已知限制：

- 自动瞄准 session 的 `mouse_delta` 是系统控制输出，不是人类原始鼠标轨迹；
- video 模式按 `video_fps` 写帧；`video_fps >= target_fps` 时不抽样，`video_fps < target_fps` 时才抽样；`events.jsonl` 的时间戳是权威时间轴；
- 当前没有游戏内绝对时间、音频、键鼠原始事件；
- 没有标签/切分；这些在 M2 补充。

---

## 6. 命名与版本

- 目录：`<source>_<YYYYmmdd_HHMMSS>`；同一秒冲突时追加 `_01`、`_02`。
- `schema_version` 变更必须写迁移说明；旧 session 不原地改。
- 新增字段保持向后兼容；删除/重命名字段需升 major。
- 采集数据默认 `research-only`；发布前做匿名化与许可证检查。

---

## 7. CS2 pilot 采集协议（M1）

在已有受控 CS2 环境中，沿用 `测试指令.txt` 的模型与参数，只增加录制参数：

```powershell
python run_real.py `
  --weights "runs\detect\cs2_detection_v2\weights\best.onnx" `
  --conf 0.35 --roi 320 --fps 30 --head-only `
  --max-mouse-step 16 --mouse-deadzone 1.0 --output-confirm-frames 3 `
  --preview `
  --record-dir runs\captures --record-fps 30 --record-scene static_target
```

建议场景矩阵（同分辨率/DPI，各 10 分钟）：

| scene | 目标运动 | 目的 |
|---|---|---|
| `static_target` | 静止/轻微晃动 | 检测稳定性、小目标 |
| `slow_strafe` | 慢速横移 | 跟踪/延迟 |
| `fast_strafe` | 快速横移/急停 | 丢失、过冲、重捕获 |

每个 session 结束后：

```powershell
python tools/check_session.py runs\captures\<session> --verify-hash
python tools/replay_session.py runs\captures\<session> --output runs\replays\<session>.mp4
```

注意：

- `run_real.py` 会显式补 `--apply-mouse`；ESC/F12 注册失败时拒绝启动；
- 仅限受控离线/私人环境，不进入联网竞技；
- 录制会占磁盘，先跑 1 分钟 smoke，再跑 10 分钟；
- 先不要开 `--record-mode frames` 做长采集，除非明确需要逐帧标注。