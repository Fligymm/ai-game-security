# P0-C 固定 F2：dust2 + nuke 平衡 10H/10B

日期：2026-11-17  
状态：**地图平衡后的 pilot；F2 仍受可见性/目标大小 confound，不能作为行为结论**

---

## 1. 数据

为消除地图与类别的共线，使用两个地图各自 5H/5B：

| 地图 | H | B |
|---|---:|---:|
| dust2 | 5 | 5 |
| nuke | 5 | 5 |
| **合计** | **10** | **10** |

H dust2：

```text
152512, 205805, 205945, 213610, 213729
```

B dust2：

```text
152746, 210201, 210336, 214003, 214446
```

H nuke：

```text
193050, 193214, 193336, 193452, 193607
```

B nuke：

```text
224959, 225112, 225221, 225359, 225515
```

所有 session 为 60s、1920×1080、static_target、first_person，并通过 timebase。
aim_botz 6H 仍隔离，不进入本分析。

---

## 2. 固定 F2 结果

F2 tracking：

```text
offset_mean_norm
offset_median_norm
offset_cv
offset_slope
settling_time_mean_s
jitter_ratio
```

LOO：

| 模型 | Accuracy | Balanced | ROC-AUC |
|---|---:|---:|---:|
| Dummy | 0.500 | 0.500 | 0.500 |
| Logistic | 0.800 | 0.800 | 0.820 |
| RandomForest | **0.850** | **0.850** | **0.900** |

---

## 3. 分地图

| 地图 | F2 Logistic Accuracy | F2 Logistic AUC |
|---|---:|---:|
| dust2 | 0.800 | 0.880 |
| nuke | 0.600 | 0.680 |

F2 在 nuke 上明显变弱，说明信号不稳定，不能假设跨地图一致。

---

## 4. Confounder

| 模型 | Accuracy | Balanced | ROC-AUC |
|---|---:|---:|---:|
| F2 only | 0.800 | 0.800 | 0.810 |
| Confounders only | 0.600 | 0.600 | 0.780 |
| F2 + confounders | 0.750 | 0.750 | 0.820 |
| **F2 residualized** | **0.550** | **0.550** | **0.550** |

地图平衡后，F2 残差化几乎回到 chance；confounders-only 仍有 0.78 AUC。

这说明：

> 不是“地图 confound 导致 F2 有效”，而是 **F2 本身仍主要编码目标可见性/
> 目标大小/置信度**。

具体：

- dust2：H visible_fraction 0.272 vs B 0.283，但 B 目标面积更大；
- nuke：H visible_fraction 0.186 vs B 0.238，B 目标面积也更大；
- 两个地图的 H/B 目标面积都不同；
- F2 在 nuke 上 AUC 仅 0.68。

---

## 5. 结论

1. 地图与类别已不再完全共线，设计比 11H/10B 更干净；
2. F2 仍然不能作为行为特征；
3. 不能训练正式分类器；
4. 不能声称 F2 跨地图泛化；
5. 当前结果仍不足以支撑论文分类结论。

---

## 6. 下一步

### 不再扩同条件数据

继续增加同条件 session 不会解决 F2 的 confound。

### 先做可见性/目标大小不变特征

候选：

1. 按目标框面积/距离归一化的 tracking error；
2. 只在可见 episode 内计算；
3. acquisition latency / visible duration；
4. 用目标面积分层后的匹配子集；
5. 对 confounder 做 residualization 后重新设计特征，而不是继续用原始 offset。

### 如果不变特征仍失败

- 停止“用视觉 tracking 误差区分 H/B”的路线；
- 改为做 benchmark/negative result 论文；
- 或在明确控制目标距离/可见性的新采集协议下重做。

---

## 7. 输出

```text
runs/eval/anticheat_p0c/features_v2_balanced_10x10/
runs/eval/anticheat_p0c/baseline_f2_balanced_10x10/
runs/eval/anticheat_p0c/confounder_balanced_10x10/
```

---

## 8. 当前决定

```text
10H/10B 地图平衡数据完成
F2 仍不可用
不训练正式分类器
不扩同条件数据
先做不变特征/可见性匹配
```