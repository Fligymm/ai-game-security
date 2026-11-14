# AI Game Security Lab

面向**多模态感知与测试数据采集**的游戏视觉实验平台：同步采集屏幕帧、感知/控制事件、时间戳与场景元数据，建立可复现的测试数据与感知基线。

研究边界：优先使用 CS2 Workshop / 离线环境、Demo / Replay、自录合法录像与开源离线 FPS。不针对真实联网竞技服务实施作弊或绕过商业反作弊；默认只做 dry-run 采集，不发送真实鼠标输入。

当前推进计划、范围与里程碑见 [`docs/PROJECT_ROADMAP.md`](docs/PROJECT_ROADMAP.md)。已完成的采集任务见 [`docs/CS2_PILOT_TASKBOOK.md`](docs/CS2_PILOT_TASKBOOK.md)；当前感知改进任务见 [`docs/PERCEPTION_TASKBOOK.md`](docs/PERCEPTION_TASKBOOK.md)，多目标补采具体流程见 [`docs/MULTITARGET_DATA_TASKBOOK.md`](docs/MULTITARGET_DATA_TASKBOOK.md)。历史架构文档 `PROJECT_FULL_ARCHITECTURE.md` 仅作背景，不再作为完成度依据。

## 安装

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 多模态采集（M1）

在不改变现有 `RealtimeAimLoop` 自动吸附链路的前提下，可选开启会话录制：

```powershell
# 干运行：只采集屏幕帧/检测/控制计划，不发送真实鼠标
python -m vision.stream.realtime_loop --frames 600 `
  --record-dir runs/captures --record-fps 60 --record-scene static_target

# 受控真实环境：本地 run_real.py 注入 Win32 hook；kill switch 失败会拒绝启动
python run_real.py --record-dir runs/captures --record-scene static_target
```

每次采集生成：

- `session.json`：session 元数据；
- `events.jsonl`：逐帧检测/选择/控制事件与 monotonic 时间戳；
- `capture.mp4`（默认）或 `frames/*.jpg`；
- `manifest.json`：文件清单、sha256、数量与质量指标。

字段与质量规则见 [`docs/DATA_CONTRACT.md`](docs/DATA_CONTRACT.md)。当前 v0 记录的是现有自动吸附链路的**感知/控制事件**；人类原始鼠标/键事件采集是后续 `human_cs2` 扩展。录制默认关闭，不影响原有实盘路径。

采集完成后校验 / 回放：

```bash
python tools/check_session.py runs/captures/<session> --verify-hash
python tools/replay_session.py runs/captures/<session> --output runs/replays/<session>.mp4
```

Pilot 完成后先抽样标注，再谈检测精度。当前 pilot 的 90 帧标注样本可用：

```powershell
python tools/sample_annotation.py `
  --pilot runs/pilot_20261114_1920x1080 `
  --output runs/pilot_20261114_1920x1080/annotation `
  --per-scene 30
```

输出 `images/`、空 `labels/` 与 `manifest.json`。具体 Label Studio 流程、类别配置和 JSON→YOLO 转换见 [`annotation/README.md`](runs/pilot_20261114_1920x1080/annotation/README.md)。`model_detections` 只是参考，不是 ground truth；没有人工标注前不能计算 mAP/recall。

90 帧标注完成后可跑部署模型的外部测试：

```powershell
python tools/evaluate_pilot.py `
  --model runs/detect/cs2_detection_v2/weights/best.onnx `
  --annotation runs/pilot_20261114_1920x1080/annotation `
  --output runs/eval/pilot_v0_onnx
```

当前结果：mAP50 0.785，conf=0.35 全类 P/R 0.910/0.718，head-only 0.860/0.695；详见 [`PERCEPTION_EVAL.md`](runs/pilot_20261114_1920x1080/PERCEPTION_EVAL.md)。90 帧是小样本外部测试，不是整体反作弊准确率。43 个漏检头中 `clear_miss` 11 个，9/11 发生在多目标帧；当前主线是补多目标数据，详见 [`HARD_EXAMPLE_ANALYSIS.md`](runs/pilot_20261114_1920x1080/hard_examples/HARD_EXAMPLE_ANALYSIS.md)。

## 仓库结构

详见 `AI_Game_Security_Lab.md` 第 16 节。
