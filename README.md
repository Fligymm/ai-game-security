# AI Game Security Lab

面向**多模态感知与测试数据采集**的游戏视觉实验平台：同步采集屏幕帧、感知/控制事件、时间戳与场景元数据，建立可复现的测试数据与感知基线。

研究边界：优先使用 CS2 Workshop / 离线环境、Demo / Replay、自录合法录像与开源离线 FPS。不针对真实联网竞技服务实施作弊或绕过商业反作弊；默认只做 dry-run 采集，不发送真实鼠标输入。公开披露仅限 [`docs/RELEASE_WHITELIST.md`](docs/RELEASE_WHITELIST.md) 中的文档/研究材料，不包含权重、原始数据、contact sheets 或真实控制代码。

> **严格禁止用于违法用途。** 本项目仅用于学习、教学和学术研究；禁止用于联网游戏作弊、绕过反作弊、未经授权控制他人设备、侵犯隐私或任何违法活动。学术研究是责任抗辩事由，不是免责金牌；法律风险边界见 [`docs/LEGAL_AND_ETHICS.md`](docs/LEGAL_AND_ETHICS.md)，使用声明见 [`docs/ACADEMIC_USE_NOTICE.md`](docs/ACADEMIC_USE_NOTICE.md)。代码和文档采用 [MIT License](LICENSE)，版权行为 `Copyright (c) 2026 Fligymm`；权重、游戏画面/标注和第三方材料不在该许可证范围内，见 [`RIGHTS.md`](RIGHTS.md) 和 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

当前推进计划、范围与里程碑见 [`docs/PROJECT_ROADMAP.md`](docs/PROJECT_ROADMAP.md)；反作弊行为检测拓展草案见 [`docs/ANTICHEAT_DEV_DRAFT.md`](docs/ANTICHEAT_DEV_DRAFT.md)（仅草案，未实现）。已完成的采集任务见 [`docs/CS2_PILOT_TASKBOOK.md`](docs/CS2_PILOT_TASKBOOK.md)；当前感知改进任务见 [`docs/PERCEPTION_TASKBOOK.md`](docs/PERCEPTION_TASKBOOK.md)，多目标补采具体流程见 [`docs/MULTITARGET_DATA_TASKBOOK.md`](docs/MULTITARGET_DATA_TASKBOOK.md)。历史架构文档 `PROJECT_FULL_ARCHITECTURE.md` 仅作背景，不再作为完成度依据。

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

`run_real.py` 当前默认使用微调前基线
`runs/detect/cs2_detection_v2/weights/best.onnx`。原因是 2026-11-16 POV 审核发现
微调模型在 1920×1080 第一人称 tiled 场景下 head 检测明显塌缩；微调模型
`runs/detect/cs2_multitarget_ft_v1/weights/best.onnx` 仅作为受限的
`experimental/cs2_multitarget_ft_v1` 分支保留，可用 `--weights` 显式启用。
策略见 [`docs/MODEL_DEFAULT_POLICY.md`](docs/MODEL_DEFAULT_POLICY.md)。

> **真实控制安全路径已修复。** 2026-11-14 审核发现 `AimController.log_only()`
> 曾向真实后端转发移动；现已改为只调用 logging-only 路径，并有 stopped/paused
> 回归测试。项目所有者已通过物理 ESC/F12 验证。仍应默认 dry-run，只通过
> `run_real.py` 显式启用真实控制，并保持 kill switch 可用。

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

不新采数据时，用已有 pilot 视频做旧/新模型离线回放：

```powershell
python tools/compare_replay_models.py `
  --output runs/eval/replay_v1_vs_v0
```

输出 `REPLAY_COMPARISON.md`、`divergence_frames.csv` 和按场景的 contact sheets。

当前结果：旧 ONNX mAP50 0.785，conf=0.35 head-only P/R 0.860/0.695；当前部署的 `cs2_multitarget_ft_v1` 在同一个 90 帧 test 上 mAP50 0.919、head mAP50 0.922、head R@0.35 0.780，空图 FP 0/6，短时 live dry-run 已通过。详见 [`PERCEPTION_EVAL.md`](runs/pilot_20261114_1920x1080/PERCEPTION_EVAL.md)、[`FINETUNE_EVAL.md`](runs/pilot_20261115_multitarget/FINETUNE_EVAL.md) 和 [`DATASET_CARD.md`](runs/pilot_20261115_multitarget/DATASET_CARD.md)。90 帧是小样本外部测试，不是整体反作弊准确率；空图 11<20 的偏差见 [`DEVIATIONS.md`](runs/pilot_20261115_multitarget/DEVIATIONS.md)。现有 3 个 pilot 视频的旧/新离线回放见 [`REPLAY_REVIEW.md`](runs/eval/replay_v1_vs_v0/REPLAY_REVIEW.md)：8,863 帧上 boxes +24.9%、empty frames -60.1%，项目所有者已复核并确认模型可收尾、不再补数据。模型卡与发布检查见 [`MODEL_CARD.md`](runs/detect/cs2_multitarget_ft_v1/MODEL_CARD.md) 和 [`OPEN_SOURCE_CHECKLIST.md`](docs/OPEN_SOURCE_CHECKLIST.md)。

## 仓库结构

详见 `AI_Game_Security_Lab.md` 第 16 节。
