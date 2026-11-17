# P0-C 地图 confound 与数据隔离

日期：2026-11-16  
状态：**地图标签已更正；nuke 5H/5B 已完成；平衡 10H/10B 结果见 `P0C_F2_BALANCED_MAPS.md`；11H/10B 结果不能使用**

---

## 1. 发现

项目所有者确认并更正：

```text
旧 5 个 H + 旧 5 个 B：dust2
新 5 个 B（224959–225515）：nuke
22:33–22:45 的 6 个 H session：aim_botz
```

当前 26 个有效 session 分布在三个地图：

```text
dust2   5H/5B
nuke    5H/5B
aim_botz 6H/0B
```

可以形成 dust2+nuke 的平衡 10H/10B；aim_botz 仍只有 H。

6 个 H session：

```text
p0b_human_20261116_223332
p0b_human_20261116_223636
p0b_human_20261116_223906
p0b_human_20261116_224217
p0b_human_20261116_224340
p0b_human_20261116_224520
```

更正前这些 session 的 `session.json` 都写着 `map = aim_botz`。
现在已按实际地图修正：

- 旧 5H / 旧 5B：`map = dust2`
- 新 5B（224959–225515）：`map = nuke`
- 6 个新 H：`map = aim_botz`

`session.json` 与 `manifest.json` 的 `session.extra.map` 已同步更新，
manifest 中 `session.json` 的 SHA256 也已重算。
`--map-name` 仍是人工填写，没有自动地图识别。

---

## 2. 影响

因此以下分析不能作为 H/B 行为结论：

```text
11H/10B F2 AUC 0.918
11H/10B confounders-only AUC 0.945
```

其中 H 组由：

```text
5 个 dust2 H
6 个 aim_botz H
```

混合；B 组由：

```text
5 个 dust2 B
5 个 nuke B
```

混合。分类器很容易学到**地图**，而不是行为。

必须按地图隔离：dust2 5H/5B 和 nuke 5H/5B 可以分别配对；
aim_botz 仍只有 H、没有 B，不能做 H/B 对比。

---

## 3. 旧地图（dust2）可用数据

旧地图（dust2）：

```text
H = 5
B = 5
```

nuke 目前：

```text
H = 5（193050–193607）
B = 5（224959–225515）
```

aim_botz 目前：

```text
H = 6
B = 0
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
2. 6 个 aim_botz H、5 个 nuke B 只能保存为 **cross-map 数据**，不能直接混用；
3. dust2 5H/5B 有一些 F2 信号，但样本太小且仍有目标面积/置信度差异；
4. 下一步需要 **5 个 nuke H**，与已有 nuke B 配对；不需要补 B；
5. 这样可形成 dust2 5H/5B + nuke 5H/5B = 10H/10B，且每个地图内类别平衡；
6. 所有新 session 必须显式填写正确地图，并人工确认。

---

## 5. 需要的新数据

已完成：**5 个 nuke H session**（与已有 nuke B 配对）：

| Session | 类型 | operator_id |
|---|---|---|
| H-11 | human / player_pov | `anon_h11` |
| H-12 | human / player_pov | `anon_h12` |
| H-13 | human / player_pov | `anon_h13` |
| H-14 | human / player_pov | `anon_h14` |
| H-15 | human / player_pov | `anon_h15` |

条件：

```text
地图：nuke（与 224959–225515 的 5 个 B 相同）
场景：static_target
60s, 1920x1080, 30 FPS
ak47, sensitivity=0.8, fov=90
first_person
old 模型默认
```

不需要新增 B；nuke 已有 5 个 B，dust2 已有 5 个 B，各补 5 个 H 后即可形成
两个地图内部 5H/5B 的平衡设计。

采集时显式传地图名，并人工确认实际地图：

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human `
  -CaptureSource player_pov `
  -OperatorId anon_h11 `
  -MapName nuke
```

依次改到 `anon_h12` … `anon_h15`。

> 新采集的 5 个 H 必须使用 `-MapName nuke`，与已有 nuke B 配对；
> 不能沿用脚本默认值或 `dust2`。

---

## 6. 下一步

1. 隔离 6 个新地图 H：不进入 H/B baseline；
2. nuke H 已完成；
3. 固定 F2，用 dust2 5H/5B + nuke 5H/5B 重跑；结果见 `P0C_F2_BALANCED_MAPS.md`；
4. 再做 confounder 分析；
5. 不训练正式分类器。

---

## 7. 当前决定

```text
11H/10B 结果作废
新地图 H 只用于后续 cross-map 实验
B 不补
nuke H 已完成；转向 F2 confound/不变特征
不训练分类器
```