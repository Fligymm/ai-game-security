# CS2 Pilot Summary

## 结论

3 个正式场景全部通过 `check_session --verify-hash`，无 errors/warnings；总有效时长 **29.74 分钟**，共 **53,436 帧**。数据可用于下一阶段的抽样标注与感知基线，但当前没有人工框标注，**不能直接声称检测精度**。

## Pilot sessions

| scene | session_id | duration | fps | frames | detections | selected | applied |
|---|---|---:|---:|---:|---:|---:|---:|
| static_target | `realtime_cs2_agent_20261114_151602` | 596.16 s | 30.0 | 17,862 | 34,909 | 9,571 (53.6%) | 6,144 (34.4%) |
| slow_strafe | `realtime_cs2_agent_20261114_152900` | 609.82 s | 29.9 | 18,259 | 40,022 | 13,403 (73.4%) | 10,547 (57.8%) |
| fast_strafe | `realtime_cs2_agent_20261114_154010` | 578.13 s | 30.0 | 17,315 | 36,299 | 9,422 (54.4%) | 5,959 (34.4%) |

合计：

```text
duration = 1784.11 s = 29.74 min
frames   = 53,436
skipped  = 0
```

## 质量门禁

- `status=closed`；
- `record_mode=video`、`video_fps=30`；
- `frames_seen = frames_recorded`，`frames_skipped=0`；
- `frame_id` 连续，无缺口；
- `timestamp_monotonic=true`；
- `effective_fps` 29.9–30.0；
- `applied_frames > 0`；
- manifest sha256 校验通过；
- 三个 replay 均可解码。

## 采集几何（已确认）

三个 session 的 `session.json` 都是：

```json
"roi": [1120, 560, 1440, 880]
```

已确认：采集桌面是 **2560x1440（2K）**，游戏窗口是居中的 **1920x1080**。`roi` 是桌面中心，不是窗口原点；几何有效。

## 数据边界

- 当前是**自动吸附链路**的感知/控制事件，不是人类原始输入。
- `detections_total` 是模型输出，不是 ground truth；90 帧标注样本用于外部测试，不参与训练。
- `track_id` 数量较多（static 1,637 / slow 1,178 / fast 1,939），有 ByteTrack 长时碎片化，需单独分析，不影响采集有效性。
- 90 帧人工标注已完成：280 个框，6 张空图；标签转换 `ok=true`。

## 感知基线（ONNX，new-environment test）

| 指标 | 数值 |
|---|---:|
| mAP50 | 0.785 |
| mAP50-95 | 0.314 |
| conf=0.35 全部类别 P / R / F1 | 0.910 / 0.718 / 0.802 |
| conf=0.35 head-only P / R / F1 | 0.860 / 0.695 / 0.769 |
| 6 张空图 conf=0.35 误报 | 0 张 / 0 框 |

分场景 mAP50：static 0.682 / slow 0.733 / fast 0.966。详见 [`PERCEPTION_EVAL.md`](PERCEPTION_EVAL.md)。

漏检分析（43 个 head）：`small` 23，`clear_miss` 11；11 个 clear_miss 中 9 个发生在 2–4 个头的多目标帧。旧训练集 86.6% 单目标，而 pilot test 有 48.8% 多目标帧。详见 [`hard_examples/HARD_EXAMPLE_ANALYSIS.md`](hard_examples/HARD_EXAMPLE_ANALYSIS.md)。

## 下一步

1. 90 帧标注与 ONNX 外部测试已完成：280 框、6 空图；
2. 做 static/slow 头部漏检错误分析：小目标、遮挡、运动模糊、标注边界分型；
3. 扩充标注样本，并固定 session-level split，避免同 session 帧泄漏；
4. 再评估跟踪/控制指标（ID switch、丢失率、reaction time）；
5. 最后再决定是否重训模型；test 帧不参与训练。