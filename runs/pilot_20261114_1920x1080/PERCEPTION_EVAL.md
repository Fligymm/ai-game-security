# Pilot Perception Evaluation

## 结论

在 90 帧人工标注的 pilot 测试集上，当前部署模型 `best.onnx` 的表现是：

- 全部类别：**mAP50 = 0.785，mAP50-95 = 0.314**
- 部署阈值 `conf=0.35`：**P = 0.910，R = 0.718，F1 = 0.802**
- `head-only`（实际控制路径）：**P = 0.860，R = 0.695，F1 = 0.769**
- 6 张空图在 `conf=0.35` 下：**0 张误报，0 个框**

这不是“模型在真实对局中 99% 准确”。这是 90 帧、3 个受控场景、单一标注者的小样本外部测试；`fast_strafe` 接近饱和，`static_target` / `slow_strafe` 的头部召回是主要瓶颈。

## 测试集

| 项目 | 数值 |
|---|---:|
| 图像 | 90 |
| 标注框 | 280 |
| `enemy_head` | 141 |
| `enemy_body` | 139 |
| 空图 | 6 |
| 场景 | static_target / slow_strafe / fast_strafe |
| 每场景 | 30 帧 |

标签来自 Label Studio 人工标注，已转换为 YOLO；90 帧不参与训练。

## 评估设置

```text
model      = runs/detect/cs2_detection_v2/weights/best.onnx
backend    = ONNX Runtime 1.23.2 / CUDAExecutionProvider
imgsz      = 640
mAP conf   = 0.001
deploy conf= 0.35
IoU match  = 0.5
device     = RTX 4070 SUPER
```

PT 和 ONNX 的差异很小：

| 模型 | mAP50 | mAP50-95 |
|---|---:|---:|
| `best.pt` | 0.782 | 0.318 |
| `best.onnx`（部署） | 0.785 | 0.314 |

## 总体指标（ONNX）

| 类别 | P | R | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| all | 0.892 | 0.762 | 0.785 | 0.314 |
| `enemy_head` | 0.828 | 0.752 | 0.745 | 0.229 |
| `enemy_body` | 0.956 | 0.773 | 0.825 | 0.399 |

身体检测明显好于头部；头部是小目标，且 `mAP50-95` 只有 0.229。

## 分场景（mAP50）

| scene | P | R | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| static_target | 0.832 | 0.660 | 0.682 | 0.261 |
| slow_strafe | 0.916 | 0.695 | 0.733 | 0.279 |
| fast_strafe | 0.944 | 0.954 | 0.966 | 0.446 |

`fast_strafe` 在这个样本上最好；`static_target` 和 `slow_strafe` 的召回明显更低。

## 部署阈值 0.35 的匹配结果

### 全部类别

| scene | images | GT | pred | TP | FP | FN | P | R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| static_target | 30 | 94 | 67 | 57 | 10 | 37 | 0.851 | 0.606 | 0.708 |
| slow_strafe | 30 | 102 | 70 | 64 | 6 | 38 | 0.914 | 0.627 | 0.744 |
| fast_strafe | 30 | 84 | 84 | 80 | 4 | 4 | 0.952 | 0.952 | 0.952 |
| **overall** | **90** | **280** | **221** | **201** | **20** | **79** | **0.910** | **0.718** | **0.802** |

### `head-only`（实际控制路径）

| scene | images | GT head | pred | TP | FP | FN | P | R | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| static_target | 30 | 47 | 33 | 27 | 6 | 20 | 0.818 | 0.574 | 0.675 |
| slow_strafe | 30 | 52 | 37 | 31 | 6 | 21 | 0.838 | 0.596 | 0.697 |
| fast_strafe | 30 | 42 | 44 | 40 | 4 | 2 | 0.909 | 0.952 | 0.930 |
| **overall** | **90** | **141** | **114** | **98** | **16** | **43** | **0.860** | **0.695** | **0.769** |

## 空图误报

```text
empty images = 6
with prediction at conf=0.35 = 0
boxes = 0
```

这 6 张空图没有误报，但样本太小，不能据此推算整体误报率。

## 解释与边界

1. **头部召回是瓶颈**：`head-only` 在 static/slow 上只有 0.574 / 0.596，fast 为 0.952。下一步应优先做 static/slow 的漏检分析，而不是直接重训。
2. **身体比头部更稳**：body 的 AP50 为 0.825，head 为 0.745；但控制路径只用 head，所以 body 指标不能替代 head 指标。
3. **空图没有误报**：6 张空图在 0.35 下全对；样本不足以证明误报率低。
4. **不能直接比较旧结果**：旧训练 val 的 mAP50 约为 0.61，但划分和场景不同；这里是新环境 pilot 测试，不是同一评测集。
5. **速度不是端到端 FPS**：日志中的 3.0 ms 是 ONNX 单图推理；实际 loop 还包含采集、跟踪、后处理和控制。
6. **未重训**：本轮只做评估，没有改变现有真实 CS2 自动吸附链路。

## 产物

- 机器可读报告：[`runs/eval/pilot_v0_onnx/eval_report.json`](../eval/pilot_v0_onnx/eval_report.json)
- 控制台日志：[`runs/eval/pilot_v0_onnx.console.log`](../eval/pilot_v0_onnx.console.log)
- 标注数据：`annotation/images/`、`annotation/labels/`、`annotation/manifest.json`
- 评测数据配置：`annotation/data.yaml`

## 下一步

1. 做 static/slow 的头部漏检错误分析：小目标、遮挡、运动模糊、标注边界，分别计数。
2. 扩充标注样本，至少覆盖更多 session；保持 test 不参与训练。
3. 若决定重训，先固定 train/val/test，再比较新模型与当前 `best.onnx`。
4. 不把本轮 90 帧结果写成“整体反作弊准确率”；它只是感知模块在受控 pilot 上的外部测试。