# P0-C 地图 confound 与数据隔离

日期：2026-11-16  
状态：**新补齐的 6 个 H session 与旧 H/B 地图不一致；11H/10B F2 结果不能使用**

---

## 1. 发现

项目所有者确认：

```text
22:33–22:45 的 6 个 H session 属于不同地图
旧 5 个 H 和所有 B session 属于旧地图
```

6 个 H session：

```text
p0b_human_20261116_223332
p0b_human_20261116_223636
p0b_human_20261116_223906
p0b_human_20261116_224217
p0b_human_20261116_224340
p0b_human_20261116_224520
```

这些 session 的 `session.json` 仍写着：

```text
map = aim_botz
scene = static_target
```

说明 `--map-name` 元数据是人工填写，**没有验证实际地图**；这次填写错误。
这是数据质量问题，不是采集工具自动识别错误。

---

## 2. 影响

因此以下分析不能作为 H/B 行为结论：

```text
11H/10B F2 AUC 0.918
11H/10B confounders-only AUC 0.945
```

其中 H 组由：

```text
5 个旧地图 H
6 个新地图 H
```

混合，而 B 组全部是旧地图。分类器很容易学到**地图/场景**，而不是行为。

必须隔离 6 个新地图 H，不能把它们与旧地图 B 混在一起做 H/B 分类。

---

## 3. 旧地图可用数据

旧地图：

```text
H = 5
B = 10（可用 5 个配对 subset）
```

旧地图 5H/5B 固定 F2 结果：

| 模型 | Accuracy | Balanced | ROC-AUC |
|---|---:|---:|---:|
| F2 only | 0.800 | 0.800 | 0.880 |
| Confounders only | 0.600 | 0.600 | 0.680 |
| F2 + confounders | 0.700 | 0.700 | 0.800 |
| F2 residualized | 0.600 | 0.600 | 0.640 |

旧地图 H/B 的可见性已基本匹配：

```text
H visible_fraction 0.272
B visible_fraction 0.283
```

但目标面积/置信度仍有差异：

```text
H target_area_median_norm 0.0008 / confidence 0.646
B target_area_median_norm 0.0016 / confidence 0.709
```

F2 residualized 后 AUC 0.640，仍不足以支持行为结论。

---

## 4. 结论

1. **11H/10B F2 结果作废**，不能写论文；
2. 6 个新地图 H 只能保存为 **cross-map 数据**，不能和旧地图 B 混用；
3. 旧地图 5H/5B 有一些 F2 信号，但样本太小且仍有目标面积/置信度差异；
4. 下一步需要**旧地图的 5 个新 H session**，而不是继续补 B；
5. 所有新 session 必须显式填写正确地图，并人工确认。

---

## 5. 需要的新数据

请求新增 **5 个旧地图 H session**：

| Session | 类型 | operator_id |
|---|---|---|
| H-11 | human / player_pov | `anon_h11` |
| H-12 | human / player_pov | `anon_h12` |
| H-13 | human / player_pov | `anon_h13` |
| H-14 | human / player_pov | `anon_h14` |
| H-15 | human / player_pov | `anon_h15` |

条件：

```text
地图：与旧 5H / 所有 B 相同（旧地图；当前记录为 aim_botz，需人工确认）
场景：static_target
60s, 1920x1080, 30 FPS
ak47, sensitivity=0.8, fov=90
first_person
old 模型默认
```

不需要新增 B；已有 10 个 B，足够选 5/10 旧地图子集。

采集时显式传地图名，并人工确认实际地图：

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human `
  -CaptureSource player_pov `
  -OperatorId anon_h11 `
  -MapName aim_botz
```

依次改到 `anon_h12` … `anon_h15`。

> 如果实际地图不是 aim_botz，请用真实地图名，不能沿用默认值。

---

## 6. 下一步

1. 隔离 6 个新地图 H：不进入 H/B baseline；
2. 等 5 个旧地图 H 采集完成；
3. 固定 F2，用 10H/10B 旧地图数据重跑；
4. 再做 confounder 分析；
5. 不训练正式分类器。

---

## 7. 当前决定

```text
11H/10B 结果作废
新地图 H 只用于后续 cross-map 实验
B 不补
请求 5 个旧地图 H
不训练分类器
```