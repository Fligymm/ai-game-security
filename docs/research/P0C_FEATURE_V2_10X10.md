# P0-C Feature v2：10H/10B 固定 F2 验证

日期：2026-11-16  
状态：**作废：11H/10B 混入 6 个新地图 H，不能用于 H/B 结论**
> 2026-11-16 后续发现：6 个 H session 属于不同地图，B 全为旧地图。
> 本文的 0.918 AUC 已被地图 confound 污染；仅保留为历史记录。
> 见 [`P0C_MAP_CONFOUND.md`](P0C_MAP_CONFOUND.md)。
> 地图平衡后的复检见 [`P0C_F2_BALANCED_MAPS.md`](P0C_F2_BALANCED_MAPS.md)。

---

## 1. 设计

在 5H/5B 上，F2 tracking 是唯一明显高于 chance 的特征族。
为避免在新增数据上重新挑特征，本轮采用**固定 F2**：

```text
offset_mean_norm
offset_median_norm
offset_cv
offset_slope
settling_time_mean_s
jitter_ratio
```

新增数据不参与特征选择；只做 leave-one-session-out 验证。

数据：

```text
H = 11 个独立 session
B = 10 个独立 session
共 21 个 session
```

（目标为 10/10；实际多出 1 个有效 H session，保留使用。）

所有 session：

```text
60s, 1920x1080, dust2 (old 5H/5B) + nuke (5B) + aim_botz (6H), static_target,
ak47, sensitivity=0.8, fov=90,
first_person, old-model tiled C, timebase PASS
```

---

## 2. 结果

固定 F2，LOO：

| 模型 | Accuracy | Balanced accuracy | ROC-AUC |
|---|---:|---:|---:|
| Dummy majority | 0.524 | 0.500 | 0.500 |
| **LogisticRegression** | **0.857** | **0.859** | **0.918** |
| RandomForest | 0.810 | 0.809 | 0.864 |

混淆矩阵（Logistic）：

```text
              pred H   pred B
true H          9        2
true B          1        9
```

错误分布在三个 session，不是单一 session 驱动：

```text
H false positives: p0b_human_20261116_152512
                   p0b_human_20261116_213610
B false negative:  p0b_game_bot_20261116_225221
```

---

## 3. F2 分布

| 特征 | H mean / median | B mean / median |
|---|---|---|
| offset_mean_norm | 3.18 / 4.02 | 1.83 / 1.90 |
| offset_median_norm | 0.81 / 0.76 | 1.11 / 1.12 |
| offset_cv | 1.62 / 1.40 | 1.22 / 1.25 |
| offset_slope | -0.003 / -0.002 | 0.002 / 0.001 |
| settling_time_mean_s | 0.126 / 0.133 | 0.118 / 0.118 |
| jitter_ratio | 0.451 / 0.448 | 0.282 / 0.278 |

H/B 出现可测的 tracking 差异，但不是完全分离：

- H 的 `offset_mean_norm` 均值更高，但中位数/分布与 B 有重叠；
- H 的 `offset_cv` 和 `jitter_ratio` 更高；
- B 的 `offset_median_norm` 更高；
- 这些差异可能混入目标距离、目标框大小、观察者视角和 selected target 差异。

---

## 4. Go/no-go

草案门限：

```text
AUC >= 0.75                   0.918 -> 通过
错误不集中在单一 session       分布在 3 个 session -> 通过
至少两个特征家族独立贡献       F2 单一家族 -> 未完全满足
```

结论：

> **固定 F2 在 10H/10B 上保持了 AUC 0.918，是明确的 pilot signal；
> 但仍是单一特征家族、单一场景、单次 LOO，不足以直接写论文结论。**

这已经足够支持下一阶段的**跨场景/跨 operator 验证**，但不支持训练正式分类器后宣称反作弊能力。

---

## 5. 当前不能做

- 不能把 0.918 写成“作弊检测准确率”；
- 不能声称 F2 能泛化到其他地图/场景；
- 不能忽略目标距离/框大小/观察者视角 confounder；
- 不能在 21 个 session 上继续调参；
- 不能重新启用 new 模型。

---

## 6. 下一步（论文级验证）

### 必须做

1. **跨场景/地图验证**：至少 2–3 个 map/scene；
2. **跨 operator/bot 配置验证**：不能只依赖同一参与者/同一 Bot；
3. **confounder 控制**：
   - 目标距离/框大小分层；
   - 按 session 归一化；
   - 检查 selected target 真实性与漏检；
4. **固定 F2 不再改特征**；
5. 报告 PR-AUC、TPR@FPR=1%、校准、置信区间；
6. 保留负结果和失败案例。

### 论文可行性

如果跨场景后 F2 仍保持 AUC ≥0.75，并且错误不是场景特异：

- 可形成“screen-only aim-tracking behavior benchmark/analysis”应用论文；
- 目标优先国内计算机应用/网络安全期刊或 Scopus/ESCI 应用期刊；
- 仍不能宣称检测真实外挂。

如果跨场景失效：

- 停止分类器路线；
- 把当前结果作为单场景 pilot/负结果；
- 不继续堆数据或调参。

---

## 7. 输出

```text
runs/eval/anticheat_p0c/features_v2_v2/
├── features_v2.csv
├── features_v2_f2.csv
├── episodes_v2.csv
└── features_v2_meta.json

runs/eval/anticheat_p0c/baseline_f2_10x10/
├── features.csv
├── loo_predictions.csv
└── baseline_results.json
```

---

## 8. 结论

**固定 F2 的 10H/10B 验证是目前最强的结果：**

```text
Logistic accuracy 0.857
AUC 0.918
错误跨 3 个 session
```

但它仍是 **tracking 单特征族 + 单场景 + 21 sessions** 的 pilot signal。
下一步不是训练分类器，而是做跨场景/跨 operator 验证。