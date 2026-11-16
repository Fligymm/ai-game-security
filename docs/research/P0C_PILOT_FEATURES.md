# P0-C Pilot：Tiled 视觉行为特征描述性分析

日期：2026-11-16  
状态：**descriptive pilot only；不是分类结果，不支持 H/B 行为差异结论**  
模型说明：**本报告基于 new `cs2_multitarget_ft_v1`；2026-11-16 已把默认回退到 old。
本报告的 head 结论不可直接迁移到 old；后续 P0-C 需明确使用哪个模型。**  
输入：

- H：`runs/eval/anticheat_cv_offline/p0b_human_20261116_152512_tiled`
- B：`runs/eval/anticheat_cv_offline/p0b_game_bot_20261116_152746_tiled`

---

## 1. 方法

从已经通过 timebase 校验的 H/B POV 视频出发：

```text
capture.mp4
 -> 3x3 tiling, tile 720
 -> YOLODetector（冻结 cs2_multitarget_ft_v1）
 -> class-aware NMS
 -> AimPipeline：TargetSelector / Kalman / trajectory / CSV log-only
 -> inference_frames.jsonl
 -> P0-C 描述性特征
```

C 推理安全属性：

```text
dry_run=true
real_control=false
apply_mouse=false
```

没有发送游戏输入，没有修改源视频和模型。

---

## 2. 数据与时间基

| 项 | H | B |
|---|---|---|
| session | `p0b_human_20261116_152512` | `p0b_game_bot_20261116_152746` |
| agent_type | `human` | `game_bot` |
| capture_source | `player_pov` | `observer_followed_bot` |
| view_mode | `first_person` | `first_person` |
| session duration | 60.27 s | 60.31 s |
| video duration | 53.47 s | 54.70 s |
| frames | 1,604 | 1,641 |
| timebase | PASS | PASS |
| source video SHA | `74a7442…` | `271ae9a…` |
| model SHA | `a142988…` | `a142988…` |

时间关联使用 `events.jsonl` 的 `timestamp_ns` 生成 `capture_time_s`，
同时保留 `video_time_s` 作为视频播放时间。

---

## 3. 描述性结果

| 指标 | H | B |
|---|---:|---:|
| 有检测帧 | 759 / 1,604（47.3%） | 1,124 / 1,641（68.5%） |
| 选中帧 | 671 / 1,604（41.8%） | 908 / 1,641（55.3%） |
| 平均检测数/帧 | 0.64 | 1.47 |
| 选中 head / body | 2 / 669 | 6 / 902 |
| 唯一选中 track | 63 | 82 |
| track switches | 82 | 115 |
| acquisition episodes | 122 | 154 |
| 选中片段平均时长 | 0.167 s | 0.177 s |
| 选中片段最长时长 | 2.52 s | 3.90 s |
| 平均 offset | 726.2 px | 653.0 px |
| 中位 offset | 913.9 px | 889.6 px |
| p95 offset | 986.8 px | 944.2 px |
| 平均选中置信度 | 0.474 | 0.518 |
| `applied_mouse=false` | 1,604 / 1,604 | 1,641 / 1,641 |

CSV 输出：

- H：671 行；
- B：908 行；
- 每行包含 `source_session_id`、`frame_index`、`video_time_s`、`capture_time_s`、`dry_run=true`。

---

## 4. 可以说什么

1. **Tiled 推理显著改善了目标覆盖。**  
   同一视频全帧直接推理只有 43/1604（H）、150/1641（B）帧有检测；
   3×3 tiling 后提升到 759/1604、1124/1641。之前低覆盖不是敌人不出现，
   而是模型输入尺度不匹配。

2. **B 的检测/选中覆盖高于 H。**  
   但这是单 session、不同视角来源、不同目标分布的描述性差异，
   不能解释为“Bot 行为更容易被检测”。

3. **两个 session 都以 body 选中为主。**  
   H 只有 2 帧选中 head，B 只有 6 帧。head 目标的尺度/检测/跟踪仍是瓶颈，
   不能只用 body 特征宣称能区分瞄准行为。

4. **track switch 数很高。**  
   H 82、B 115，均接近或超过 acquisition episode 数；ByteTrack ID 稳定性
   仍需检查，不能把这些 ID 变化直接当作行为差异。

5. **offset 不是实际鼠标输入。**  
   这里的 offset 是 AimPipeline 计算出的目标误差/规划偏移，不是玩家真实
   mouse delta，也不是作弊证据。

---

## 5. 不能说什么

- 不能说 H 和 B 的行为差异已经成立；
- 不能说这些特征能检测真实外挂；
- 不能用一个 H、一个 B session 做分类或统计推断；
- 不能把 `enemy_body` 选中率当作瞄准行为；
- 不能把 track switch 直接解释为目标切换行为；
- 不能忽略检测误报、跟踪失败和 observer 视角差异。

当前样本量：

```text
H = 1 session
B = 1 session
map = aim_botz
scene = static_target
```

这是 pilot 特征管线验证，不是 H/B 分类实验。

---

## 6. 输出文件

```text
runs/eval/anticheat_p0c/pilot_tiled_v1/
├── frames.csv              # 逐帧检测/选中/offset/capture_time
├── session_summary.csv     # 两 session 汇总
└── summary.json            # 来源、SHA、详细 episodes
```

提取工具：

```text
tools/extract_p0c_features.py
```

---

## 7. 下一步建议

### P0-C-1：视觉质量人工复核（优先）

- 每个 session 抽取 20–30 帧，检查 selected target 是否真实、是否误报；
- 重点看 head 为何几乎不被选中；
- 检查 track switch 是否由检测抖动/遮挡引起。

### P0-C-2：扩大 H/B pilot

- 每个类别至少 3 个独立 session；
- 同一 map/scene/weapon/FOV；
- 保留 `capture_time_s` 和 source SHA；
- 每次重新检查 `TIMEBASE_CONSISTENT`。

### P0-C-3：再谈特征对比

只有完成上述复核和扩样后，才适合做：

- H vs B 描述统计；
- 特征分布/消融；
- 会话级分类 baseline。

当前不建议训练分类器，也不建议把 B 的高覆盖解释为行为差异。

---

## 8. 自动 QC 补充（2026-11-16）

### 9.1 原始检测类别

| 检测类别 | H | B |
|---|---:|---:|
| head detections | 3 | 7 |
| body detections | 1,025 | 2,400 |
| selected head | 2 | 6 |
| selected body | 669 | 902 |

head 检测几乎消失，不是 `TargetSelector` 没有优先选 head；是检测器在
1920×1080 POV + tiling 下几乎没有输出 head。降低 conf 到 0.15 的抽样测试
仍只有 0–2 个 head 检测，说明这不是单纯阈值问题。

### 9.2 选中跟踪片段

| 指标 | H | B |
|---|---:|---:|
| selected runs | 137 | 190 |
| run 长度中位数 | 2 帧 | 2 帧 |
| run 长度均值 | 4.9 帧 | 4.8 帧 |
| run 最长长度 | 70 帧 | 110 帧 |
| ≤2 帧的 run | 82 | 119 |
| run 时长中位数 | 0.037 s | 0.034 s |
| selected gaps >0.1 s | 84 | 106 |

track switch 中大部分切换框的 IoU 接近 0；它们更像是目标消失/重新捕获或
检测抖动，而不是可解释的“目标切换行为”。当前 track ID 不适合直接作为
行为特征。

### 9.3 QC 可视化

已生成 20 帧/session 的 contact sheets：

```text
runs/eval/anticheat_p0c/pilot_tiled_v1/qc/contact_sheet_human.jpg
runs/eval/anticheat_p0c/pilot_tiled_v1/qc/contact_sheet_game_bot.jpg
runs/eval/anticheat_p0c/pilot_tiled_v1/qc/qc_samples_*.json
```

生成工具：[`tools/make_p0c_qc.py`](../../tools/make_p0c_qc.py)

**人工视觉复核尚未完成**：contact sheet 需要确认 selected box 是否覆盖真实目标、
是否存在 body 误报，以及 track switch 是否为目标切换而非 ID 抖动。

## 9. 结论

**P0-C 管线已跑通，但当前结果只是描述性 pilot。**

最重要的发现不是 H/B 差异，而是：

> 320 ROI 检测器直接跑 1920×1080 POV 会严重漏检；3×3 tiling 后覆盖率恢复，
> 但 body 主导、head 稀少和 track ID 抖动仍是下一阶段必须解决的问题。