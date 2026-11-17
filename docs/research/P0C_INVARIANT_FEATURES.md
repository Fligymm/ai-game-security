# P0-C 不变特征与匹配分析

日期：2026-11-17  
状态：**negative pilot；F2 路线不建议继续**

---

## 1. 目的

F2 在平衡 10H/10B 上仍有较高 AUC，但对 confounder 残差化后只剩 0.55。
本步尝试两种不改数据的方案：

1. 尺度不变特征；
2. 目标面积/可见性匹配子集。

---

## 2. 新增不变特征

在 Feature v2 中新增：

```text
offset_slope_norm_median
settling_fraction_mean
offset_drop_ratio_mean
offset_iqr_ratio_mean
```

并只使用尺度无关的 6 个特征：

```text
offset_cv
jitter_ratio
offset_slope_norm_median
settling_fraction_mean
offset_drop_ratio_mean
offset_iqr_ratio_mean
```

输出：

```text
runs/eval/anticheat_p0c/features_v2_invariant_10x10/
```

---

## 3. 不变特征 baseline

平衡 10H/10B，LOO：

| 模型 | Accuracy | Balanced | ROC-AUC |
|---|---:|---:|---:|
| Dummy | 0.500 | 0.500 | 0.500 |
| Logistic | 0.700 | 0.700 | 0.750 |
| RandomForest | 0.650 | 0.650 | 0.700 |

Confounder 复检：

| 模型 | Accuracy | ROC-AUC |
|---|---:|---:|
| Invariant only | 0.750 | 0.740 |
| Confounders only | 0.600 | 0.780 |
| Invariant + confounders | 0.750 | 0.780 |
| **Invariant residualized** | **0.500** | **0.570** |

结论：

> 尺度不变化没有解决 confound；残差化后仍接近 chance。

---

## 4. 目标面积/可见性匹配

按 `target_area_median_norm` + `visible_fraction` 做 1:1 最近匹配：

| 匹配阈值 | pairs | Logistic Accuracy | Logistic AUC |
|---|---:|---:|---:|
| 0.8 SD | 4 | 0.625 | 0.750 |
| 1.0 SD | 5 | 0.600 | 0.760 |
| 1.5 SD | 5 | 0.600 | 0.760 |
| 2.0 SD | 6 | 0.500 | 0.667 |

匹配子集 AUC 约 0.75–0.76，但 accuracy 仅 0.60；样本只有 4–6 对，不能支持结论。

---

## 5. 结论

1. 地图平衡后 F2 仍受目标面积/可见性影响；
2. 尺度不变特征没有恢复信号；
3. 目标面积/可见性匹配后，F2 的 accuracy 接近 chance；
4. 当前数据不能支持“视觉 tracking error 可区分 H/B”的论文结论；
5. 不建议继续扩同条件数据，也不建议训练正式分类器。

---

## 6. 论文路线判断

### 不建议

```text
继续调 F2
继续加同条件 session
把 0.90 AUC 写成检测能力
```

### 可行但需要重新定义问题

1. **Benchmark / negative result 论文**  
   主题：小样本屏幕视觉行为特征在 H/B 上的可复现性与 confound 分析。  
   贡献是实验设计和负结果，不是高准确率分类。

2. **控制采集条件的 tracking 研究**  
   如果要继续 tracking error 假设，需要重新采集：
   - H/B 目标距离/目标大小匹配；
   - 可见性/遮挡匹配；
   - 固定 Bot/目标位置；
   - 每类更多独立 session。

3. **换行为问题**  
   不再用“offset 大小”区分 H/B，改用更明确的行为事件（目标获取、切换、修正序列），并先做预注册特征。

---

## 7. 当前决定

```text
F2 tracking 路线暂停
不训练正式分类器
不扩同条件数据
先决定论文定位：negative/benchmark 还是重新设计采集
```

---

## 8. 输出

```text
runs/eval/anticheat_p0c/features_v2_invariant_10x10/
runs/eval/anticheat_p0c/baseline_invariant_10x10/
runs/eval/anticheat_p0c/confounder_invariant_10x10/
```