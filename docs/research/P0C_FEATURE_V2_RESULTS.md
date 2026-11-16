# P0-C Feature v2：首轮 5H/5B 结果

日期：2026-11-16  
状态：**conditional pilot signal；不是分类器结论**

---

## 1. 实现

新增：

```text
tools/extract_p0c_features_v2.py
```

输入：

```text
runs/eval/anticheat_cv_offline/<session>_v0_tiled/inference_frames.jsonl
```

输出：

```text
runs/eval/anticheat_p0c/features_v2_v1/
├── features_v2.csv
├── episodes_v2.csv
└── features_v2_meta.json
```

实现边界：

- 仅读取 existing old-model tiled 输出；
- 不重跑检测/跟踪；
- 不修改模型、ByteTrack、AimPipeline；
- 不扩数据；
- 不训练正式分类器。

Feature v2 包含 F1 acquisition、F2 tracking、F3 correction、F4 switching、
F5 visibility，共 25 个 session-level 特征。

---

## 2. 5H/5B 首轮 baseline

Leave-one-session-out，13 → 25 特征：

| 特征集 | 模型 | Accuracy | Balanced | ROC-AUC |
|---|---|---:|---:|---:|
| v1 | Logistic | 0.600 | 0.600 | 0.680 |
| v1 | RandomForest | 0.600 | 0.600 | 0.720 |
| v2 全特征 | Logistic | 0.600 | 0.600 | 0.600 |
| v2 全特征 | RandomForest | 0.700 | 0.700 | 0.800 |

v2 全特征略优于 v1 的 RF AUC，但仍只有 7/10 正确，不能作为可靠分类。

---

## 3. 特征家族 ablation

| 特征族 | RF Accuracy | RF AUC | Logistic Accuracy | Logistic AUC |
|---|---:|---:|---:|---:|
| F1 acquisition | 0.100 | 0.000 | 0.200 | 0.000 |
| **F2 tracking** | **0.800** | **0.920** | **0.800** | **0.840** |
| F3 correction | 0.400 | 0.280 | 0.500 | 0.560 |
| F4 switching | 0.400 | 0.440 | 0.600 | 0.560 |
| F5 visibility | 0.500 | 0.440 | 0.600 | 0.560 |
| ALL | 0.700 | 0.800 | 0.600 | 0.600 |

关键发现：

- **F2 tracking 是唯一明显高于 chance 的特征族**；
- F2 的 `offset_median_norm` 和 `offset_cv` 在 H/B 上可见分离：
  - H median offset 约 0.55–0.69；
  - B median offset 约 0.79–1.54；
  - H offset CV 整体更高，B 更集中；
- 但 H/B 有重叠，且只有 5 vs 5；
- F1/F3/F4/F5 单独几乎无效；
- 全特征加入弱特征后反而降低 RF AUC（0.92 → 0.80），说明高维小样本下会稀释信号。

F2 结果不能直接解释为“作弊行为差异”，更可能是：

- 目标距离/目标框大小差异；
- selected target 的 tracking error；
- 或观察者视角差异。

需要扩样和 confounder 控制后验证。

---

## 4. Go/no-go 判断

草案门限：

```text
AUC >= 0.75                    F2 RF 0.92 / Logistic 0.84  -> 通过
错误不集中在单一 session        F2 仍需逐 session 检查
至少两个特征家族独立贡献       只有 F2 明显贡献 -> 未通过
```

结论：

> **条件性信号，不是 go。**  
> F2 tracking 有可重复的 pilot 信号，但只有一个家族、只有 10 个 session，
> 还不能支持论文分类结论。

---

## 5. 当前决定

```text
不训练正式分类器
不把 F2 结果写成“检测能力”
不继续在这 10 个 session 上调参
保留 F1–F5 全特征作为后续消融
```

下一步需要：

1. 用 **F2 预先指定的特征**，扩到 10H/10B；
2. 新 session 不参与特征选择；
3. 做 leave-one-session-out + 逐 session 错误分析；
4. 若 F2 在 10H/10B 仍保持 AUC ≥0.75，再考虑论文级验证；
5. 若 F2 失效，则回到特征设计，而不是继续扩数据。

---

## 6. 输出

```text
runs/eval/anticheat_p0c/features_v2_v1/
runs/eval/anticheat_p0c/baseline_v2_features/
runs/eval/anticheat_p0c/ablation_v2/ablation.json
```

---

## 7. 结论

Feature v2 发现了 **F2 tracking 的 pilot 信号**，但还没有达到论文可用的证据强度。

这是目前最值得追的方向，但下一步应是：

> **固定 F2 特征，扩到 10H/10B 做验证；不要再用全特征调参。**

body 少量漏检仍作为 accepted limitation，不阻断本轮。