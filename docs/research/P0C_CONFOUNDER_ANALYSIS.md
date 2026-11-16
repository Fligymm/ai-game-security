# P0-C F2 confounder 分析

日期：2026-11-16  
状态：**F2 signal 主要可由可见性/目标大小解释；不能作为行为结论**
> 后续补充：21-session 数据同时混入 6 个新地图 H。地图 confound 使本文结论更强：
> 当前数据不能用于 H/B 分类。见 [`P0C_MAP_CONFOUND.md`](P0C_MAP_CONFOUND.md)。

---

## 1. 目的

固定 F2 tracking 特征在 11H/10B 上达到较高 LOO 指标：

```text
Logistic accuracy 0.857
AUC 0.918
```

但 H/B 的目标可见性、目标大小、观察者视角不同，必须检查 F2 是否只是这些
confounder 的代理。

---

## 2. 方法

F2：

```text
offset_mean_norm
offset_median_norm
offset_cv
offset_slope
settling_time_mean_s
jitter_ratio
```

Confounders：

```text
target_area_median_norm
visible_fraction
target_confidence_mean
visible_duration_median_s
selected_fraction_of_visible
```

分析：

1. Spearman 相关；
2. LOO Logistic：
   - F2 only
   - confounders only
   - F2 + confounders
   - F2 residualized against confounders（在每个训练折内拟合残差）

---

## 3. 结果

| 模型 | Accuracy | Balanced | ROC-AUC |
|---|---:|---:|---:|
| F2 only | 0.905 | 0.905 | 0.936 |
| confounders only | 0.905 | 0.909 | 0.945 |
| F2 + confounders | 0.857 | 0.859 | 0.964 |
| **F2 residualized** | **0.619** | **0.618** | **0.645** |

关键：

> **单独使用 confounder 可以达到与 F2 相当甚至更高的 AUC；
> 把 F2 对 confounder 残差化后，AUC 降到 0.645。**

这说明 F2 的判别力很大一部分来自目标可见性/目标大小，而不是
H/B 的跟踪行为差异。

---

## 4. H/B 可见性差异

| 指标 | H mean | B mean |
|---|---:|---:|
| visible_fraction | 0.534 | 0.261 |
| target_area_median_norm | 0.0007 | 0.0017 |
| selected_fraction_of_visible | 0.749 | 0.795 |
| target_confidence_mean | 0.659 | 0.713 |

B 的目标更大、可见比例更低，H/B 的采集条件并不匹配。

相关示例：

```text
offset_mean_norm   vs selected_fraction_of_visible  rho -0.716
jitter_ratio       vs selected_fraction_of_visible  rho -0.701
jitter_ratio       vs visible_fraction              rho  0.682
offset_cv          vs target_area_median_norm       rho -0.666
offset_median_norm vs target_confidence_mean        rho  0.499
```

---

## 5. 结论

1. F2 的 0.918 AUC **不能解释为 H/B 行为差异**；
2. F2 主要编码：
   - 目标是否容易看见；
   - 目标框大小/距离；
   - selected target 的可见性；
3. confounder-only 也能达到 0.945 AUC，说明当前数据存在明显采集偏差；
4. F2 residualized 后仅 0.645，不能支持论文级行为结论；
5. 不能训练正式分类器，也不能用当前 11H/10B 直接写论文。

---

## 6. 下一步

### 优先：可见性匹配（不一定要立刻采新数据）

1. 在现有视频中按 `visible_fraction`、`target_area_median_norm` 分层；
2. 对 H/B 做匹配子集，重新评估 F2；
3. 或设计 **可见性不变特征**：
   - 相对 tracking error（按目标框归一化）；
   - acquisition latency / visible duration；
   - 只在可见 episode 内比较；
   - 控制 target area 后的残差特征。

### 如果匹配后 F2 仍失效

需要采集 **可见性匹配的 H/B 数据**：

- 控制目标距离/目标大小；
- 控制目标可见比例；
- H/B 同一场景、同一 Bot/目标分布；
- 不能只增加同场景 session。

### 如果匹配后 F2 仍有信号

- 再做跨场景/跨 operator；
- 才可能支撑论文。

---

## 7. 输出

```text
runs/eval/anticheat_p0c/confounder_v1/
├── confounder_results.json
├── correlations.csv
└── model_comparison.csv
```

工具：

[`tools/analyze_p0c_confounders.py`](../../tools/analyze_p0c_confounders.py)

---

## 8. 当前决定

```text
不训练正式分类器
不把 F2 0.918 写成检测准确率
不继续扩同条件数据
先做可见性匹配/不变特征
```

这是目前最重要的负结果：**F2 的高 AUC 很可能是采集可见性差异，而不是行为差异。**