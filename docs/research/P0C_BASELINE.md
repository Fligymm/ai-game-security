# P0-C：3H/3B 简单 baseline

日期：2026-11-16  
状态：**pilot negative result；不能作为分类器或论文结论**

---

## 1. 目的

在 3 H / 3 B 的 old-model P0-C 特征上做最简单的 session-level baseline，
验证当前特征是否已经具备可分性。

这不是模型训练，不修改冻结模型，也不用于真实控制。

---

## 2. 数据与方法

输入：

```text
runs/eval/anticheat_p0c/pilot_old_tiled_v2/summary.json
H = 3 sessions
B = 3 sessions
```

特征：

```text
detection_frame_ratio
selected_frame_ratio
mean_detections_per_frame
selected_head_ratio
unique_selected_tracks
track_switches_per_frame
acquisition_episodes_per_frame
selected_episode_duration_mean_s
selected_episode_duration_max_s
mean_offset_px
median_offset_px
p95_offset_px
mean_selected_confidence
```

评估：

```text
Leave-One-Session-Out
Dummy majority baseline
LogisticRegression
RandomForest (max_depth=2)
```

为什么用 LOO：

- 只有 6 个 session；
- 按 session 留出，避免窗口/帧级泄漏；
- 不把同 session 的帧拆到 train/test。

---

## 3. 结果

| 模型 | accuracy | balanced accuracy | ROC-AUC |
|---|---:|---:|---:|
| Dummy majority | 0.500 | 0.500 | 0.500 |
| LogisticRegression | **0.667** | **0.667** | 0.556 |
| RandomForest (depth=2) | 0.333 | 0.333 | 0.222 |

混淆矩阵/预测见：

```text
runs/eval/anticheat_p0c/baseline_v2/loo_predictions.csv
runs/eval/anticheat_p0c/baseline_v2/baseline_results.json
```

Logistic 的 4/6 正确率不能解释为“检测到行为差异”：

- n=6；
- 3/3 类别；
- 单一 map/scene/weapon；
- 特征来自同一个 old 模型和同一种 tiling；
- LOO 每折只有 5 个训练样本。

RandomForest 低于 chance，说明在这个样本量下树模型没有稳定信号。

---

## 4. 结论

**当前 3H/3B 特征不支持可靠分类。**

可以保留为：

- 特征管线 smoke test；
- baseline 负结果；
- 后续扩样后的对照。

不能用于：

- 论文分类结论；
- “检测作弊”宣称；
- 生产反作弊；
- 直接用这 6 个 session 训练正式模型。

---

## 5. 已接受的 body 漏检问题

人工 QC 已确认：

- 目标覆盖总体良好；
- 少量 body 漏扫；
- 原因是训练样本少、body 动作变化后失去传统站立特征；
- 样例数极少。

处理：

```text
记录为 accepted limitation
不因此重训模型
不作为本轮阻断
后续扩样时再考虑是否补充 body 姿态样本
```

---

## 6. 下一步

1. 不继续在这 6 个 session 上调参追 accuracy；
2. 扩样后再做 cross-session baseline；
3. 先确认 head/body 特征稳定性，再决定是否使用分类模型；
4. 需要更大样本时，再提出定向数据扩展请求。

---

## 7. 运行方式

```powershell
.\.venv\Scripts\python.exe tools\run_p0c_baseline.py `
  --summary runs\eval\anticheat_p0c\pilot_old_tiled_v2\summary.json `
  --output-dir runs\eval\anticheat_p0c\baseline_v2
```

输出：

```text
runs/eval/anticheat_p0c/baseline_v2/
├── features.csv
├── loo_predictions.csv
└── baseline_results.json
```