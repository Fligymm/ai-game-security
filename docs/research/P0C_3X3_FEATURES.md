# P0-C：3×3 tiled old-model 特征汇总

日期：2026-11-16  
状态：**descriptive only；3 H / 3 B；未训练分类器**  
模型：

```text
runs/detect/cs2_detection_v2/weights/best.onnx
tile_size=720, grid=3, conf=0.35, iou=0.5
```

输入 H：

- `p0b_human_20261116_152512`
- `p0b_human_20261116_205805`
- `p0b_human_20261116_205945`

输入 B：

- `p0b_game_bot_20261116_152746`
- `p0b_game_bot_20261116_210201`
- `p0b_game_bot_20261116_210336`

所有 session：

```text
60s, 1920x1080, dust2, static_target,
ak47, sensitivity=0.8, fov=90, first_person
timebase PASS
```

---

## 1. Session-level

| Session | Agent | detect% | select% | head/body | tracks | switches | episodes | mean offset |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `..._152512` | H | 36.7 | 30.7 | 132 / 360 | 54 | 66 | 93 | 80.7 |
| `..._205805` | H | 22.9 | 19.0 | 79 / 246 | 35 | 40 | 63 | 105.4 |
| `..._205945` | H | 32.6 | 24.4 | 237 / 184 | 50 | 65 | 65 | 76.8 |
| `..._152746` | B | 35.6 | 28.8 | 129 / 344 | 67 | 75 | 89 | 106.8 |
| `..._210201` | B | 24.5 | 20.3 | 182 / 156 | 57 | 60 | 74 | 144.3 |
| `..._210336` | B | 19.0 | 16.8 | 124 / 155 | 39 | 42 | 52 | 65.2 |

---

## 2. 3 H vs 3 B 汇总

| 指标 | H mean [min–max] | B mean [min–max] |
|---|---|---|
| detection frame ratio | 30.7% [22.9–36.7] | 26.3% [19.0–35.6] |
| selected frame ratio | 24.7% [19.0–30.7] | 22.0% [16.8–28.8] |
| mean detections/frame | 0.409 [0.273–0.505] | 0.362 [0.266–0.457] |
| selected head total | 448 | 435 |
| selected body total | 790 | 655 |
| selected head ratio | 36.2% | 39.9% |
| unique selected tracks mean | 46.3 | 54.3 |
| track switches mean | 57.0 | 59.0 |
| acquisition episodes mean | 73.7 | 71.7 |
| mean episode duration | 0.164 s | 0.146 s |
| mean offset | 87.6 px | 105.4 px |
| median offset | 47.9 px | 74.1 px |
| p95 offset | 309.1 px | 392.9 px |
| mean selected confidence | 0.640 | 0.693 |

---

## 3. 观察

### 3.1 可以说的

- old 模型在 3 H / 3 B 上都恢复了 head 检测；
- H/B 的 selected head 比例接近（约 36% / 40%），不再是 new 模型的 head 塌缩；
- H/B 的检测/选中覆盖、episode 数、track switch 数范围重叠明显；
- H 的 mean/median offset 略低于 B，但单 session 范围重叠，不能据此下行为结论；
- 所有输出均为 `dry_run=true`、`real_control=false`、`apply_mouse=false`。

### 3.2 不能说的

- 不能说 H 和 B 的行为差异已经成立；
- 不能把 offset 差异直接解释为“作弊”或“玩家水平”；
- 不能用 3 vs 3 做显著性检验并宣称泛化；
- 不能把 track switch 直接当作目标切换；
- 不能忽略目标存在时间短造成的 episode 碎片化；
- 不能把 old 模型的这些特征和 new 模型特征混用。

### 3.3 样本限制

```text
每类 3 个 session
单一 map / scene / weapon
单一 FOV / sensitivity
单一玩家/设备组（H）
单一 Observer Bot 配置（B）
```

这仍是 pilot，不是统计显著的 H/B 分类数据集。

---

## 4. QC 状态

原始 H/B 的 old-model contact sheets 已由所有者人工 QC 通过：

```text
目标覆盖好
跟踪时间符合要求
碎片化主要因为目标存在时间短
```

新增 4 个 session 的 QC sheets 已生成：

```text
runs/eval/anticheat_p0c/pilot_old_tiled_v2/qc/<session>/contact_sheet_*.jpg
```

**新增 4 个 session 的人工视觉复核仍待完成。**  
在复核完成前，不把 3 H / 3 B 视为最终可用数据集。

---

## 5. 输出

```text
runs/eval/anticheat_p0c/pilot_old_tiled_v2/
├── frames.csv
├── session_summary.csv
├── summary.json
└── qc/
    ├── p0b_human_20261116_152512_v0_tiled/
    ├── p0b_human_20261116_205805_v0_tiled/
    ├── p0b_human_20261116_205945_v0_tiled/
    ├── p0b_game_bot_20261116_152746_v0_tiled/
    ├── p0b_game_bot_20261116_210201_v0_tiled/
    └── p0b_game_bot_20261116_210336_v0_tiled/
```

---

## 6. 简单 baseline

已在 3H/3B 上做 leave-one-session-out baseline：

```text
Dummy majority        accuracy 0.500
LogisticRegression    accuracy 0.667, AUC 0.556
RandomForest depth=2  accuracy 0.333, AUC 0.222
```

**当前特征不支持可靠分类**；详见
[`P0C_BASELINE.md`](P0C_BASELINE.md)。

body 少量漏检已记录为 accepted limitation：训练样本少、body 动作变化后
失去传统站立特征；样例极少，不作为本轮阻断，后续扩样再考虑补充。

## 7. 下一步

1. 人工复核新增 4 个 session 的 contact sheets；
2. 复核通过后，做 leave-one-session-out 的描述性稳定性检查；
3. 暂不训练分类器；先检查特征在 session 间的方差；
4. 若特征稳定，再决定是否增加更多 session 或做简单 baseline；
5. 继续使用 old 模型；new 模型只在 experimental 分支。

---

## 7. 结论

**P0-C 的 3 H / 3 B 特征管线已经跑通，old 模型恢复了 head/body 的合理比例；
但 3 vs 3 仍只能做描述性分析，不能做行为分类结论。**

当前最大价值是把“模型 head 塌缩”问题排除，并建立了可重复的
H/B P0-C 特征和 QC 管线。