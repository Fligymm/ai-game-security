# CS2 Pilot Notes（1920x1080 窗口）

## 环境

- CS2 版本：待确认
- 地图：aimbotz
- 桌面分辨率：2560x1440（2K，已确认）
- 游戏窗口分辨率：1920x1080（居中窗口，已确认）
- 显示模式：窗口模式
- Windows 缩放：待确认（建议 100%）
- 鼠标 DPI：1600
- 灵敏度：0.80（eDPI 1280）
- FOV：CS 默认（90）
- bot / 目标：静态 bot；slow/fast 通过玩家左右移动制造相对运动
- 采集后端：bettercam / CUDAExecutionProvider
- 模型：`runs\detect\cs2_detection_v2\weights\best.onnx`
- 固定参数：`conf=0.35 roi=320 fps=30 head-only max-step=16 deadzone=1.0 confirm=3 record-fps=30`

## 采集几何

已确认：2560x1440 桌面上运行居中的 1920x1080 窗口，所以 `ScreenGrabber` 抓屏幕中心：

```json
"roi": [1120, 560, 1440, 880]
```

三个 pilot 的 `session.json` 都是这个值，说明采集几何一致；窗口居中已确认。若以后调整窗口位置/缩放，ROI 与准星的对应关系需要重新检查。

> 若桌面本身是 1920x1080，ROI 才会是 `[800, 380, 1120, 700]`；本次不是这种情况。

## Sessions

| session_id | scene | start | duration_s | effective_fps | frames_recorded | detections | selected | applied | check |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `realtime_cs2_agent_20261114_151320` | smoke_dry_1920 | 15:13 | 11.51 | 26.1 | 300 | 468 | 108 | 0 | ok |
| `realtime_cs2_agent_20261114_151503` | smoke_real_1920 | 15:15 | 12.29 | 24.4 | 300 | 762 | 190 | 116 | ok |
| `realtime_cs2_agent_20261114_151602` | static_target | 15:16 | 596.16 | 30.0 | 17,862 | 34,909 | 9,571 | 6,144 | ok |
| `realtime_cs2_agent_20261114_152900` | slow_strafe | 15:29 | 609.82 | 29.9 | 18,259 | 40,022 | 13,403 | 10,547 | ok |
| `realtime_cs2_agent_20261114_154010` | fast_strafe | 15:40 | 578.13 | 30.0 | 17,315 | 36,299 | 9,422 | 5,959 | ok |

## 质量摘要

- 三个正式 session 全部 `check_session --verify-hash` 通过，`warnings=[]`。
- 总有效时长：`1784.11 s = 29.74 min`；总帧数：`53,436`。
- `frames_skipped=0`，`frame_id` 连续无缺口。
- `timestamp_monotonic=true`，无回退时间戳。
- 三个 session 的 ROI 均为 `[1120,560,1440,880]`，`record_mode=video`，`video_fps=30`。
- 选中率：
  - static_target：`9571/17862 = 53.6%`
  - slow_strafe：`13403/18259 = 73.4%`
  - fast_strafe：`9422/17315 = 54.4%`
- 实际发送率：
  - static_target：`6144/17862 = 34.4%`
  - slow_strafe：`10547/18259 = 57.8%`
  - fast_strafe：`5959/17315 = 34.4%`
- 检测类别计数（head/body）：
  - static_target：head 16,472 / body 18,437
  - slow_strafe：head 19,244 / body 20,778
  - fast_strafe：head 15,400 / body 20,899
- 每帧最多检测数：static 8 / slow 16 / fast 9；track id 数分别为 1,637 / 1,178 / 1,939（ByteTrack 长时碎片化，后续单独分析，不影响采集有效性）。
- 已生成标注样本：`annotation/`，3 个 scene 各 30 帧 = 90 帧；60 帧有模型选中、30 帧无选中。
- 90 帧已人工标注：280 个框、6 张空图；部署 ONNX 外部测试 mAP50=0.785，conf=0.35 全类 P/R=0.910/0.718，head-only P/R=0.860/0.695；空图 0 误报。

## 异常 / 记录

- 旧 2560x1440 目录 `runs\pilot_20261114` 已标记为历史，不混入本数据集。
- 真实控制入口使用 `GetAsyncKeyState` 轮询兜底（F12 被其他程序占用）；ESC/F12 可用。
- `smoke_real_1920` 证明真实后端可发送：`applied_frames=116`。
- 三个正式 session 均通过 PASS 门禁；未发现需要重跑的采集错误。