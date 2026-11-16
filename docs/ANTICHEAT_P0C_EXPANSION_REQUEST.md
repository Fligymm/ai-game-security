# P0-C 数据集扩展请求

日期：2026-11-16  
状态：**等待项目所有者采集；未自动扩样**

---

## 1. 当前通过 QC 的样本

人工 QC（项目所有者）已确认：

```text
H 目标覆盖好，跟踪时间符合要求
B 目标覆盖好，跟踪时间符合要求
碎片化主要因为目标存在时间短
```

当前可用：

```text
H  p0b_human_20261116_152512
B  p0b_game_bot_20261116_152746
```

两个 session 都是：

```text
60s, 1920x1080, dust2, static_target, ak47,
sensitivity=0.8, fov=90, first_person
old model default
```

---

## 2. 请求扩展的最小数据

请求新增 **2 个 H + 2 个 B**，使每类达到 **3 个独立 session**：

| Session | agent_type | capture_source | operator_id |
|---|---|---|---|
| H-02 | human | player_pov | `anon_h02` |
| H-03 | human | player_pov | `anon_h03` |
| B-02 | game_bot | observer_followed_bot | `anon_b02` |
| B-03 | game_bot | observer_followed_bot | `anon_b03` |

要求：

- 每次独立启动 CS2/观察者 session；
- 不复用同一录像切帧；
- 保持同一 map/scene/weapon/FOV/sensitivity；
- 60 秒左右；
- 第一人称；
- B 只使用 CS2 内置 Bot + 观察者第一人称；无法稳定跟随时停止，不降级第三人称；
- 不采集账号、聊天、语音、玩家名。

暂不要求多地图；先完成同场景 3/class，再做 cross-scene。

---

## 3. H 采集命令

```powershell
.\.venv\Scripts\python.exe tools\capture_fps_pilot.py `
  --agent-type human `
  --capture-source player_pov `
  --view-mode first_person `
  --scene static_target `
  --map-name dust2 `
  --weapon ak47 `
  --sensitivity 0.8 `
  --fov 90 `
  --duration 60 `
  --operator-id anon_h02 `
  --output-dir runs\captures\p0b_pilot `
  --attest-pov `
  --attest-experiment `
  --confirm-offline
```

第二个人类 session 把 `--operator-id` 改为 `anon_h03`。

---

## 4. B 采集命令

```powershell
.\.venv\Scripts\python.exe tools\capture_fps_pilot.py `
  --agent-type game_bot `
  --capture-source observer_followed_bot `
  --view-mode first_person `
  --scene static_target `
  --map-name dust2 `
  --weapon ak47 `
  --sensitivity 0.8 `
  --fov 90 `
  --duration 60 `
  --operator-id anon_b02 `
  --output-dir runs\captures\p0b_pilot `
  --attest-pov `
  --attest-experiment `
  --confirm-offline
```

第二个 Bot session 把 `--operator-id` 改为 `anon_b03`。

---

## 5. 每次采集后的校验

```powershell
$session = Get-ChildItem runs\captures\p0b_pilot -Directory |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
.\.venv\Scripts\python.exe tools\check_fps_pilot.py $session.FullName --verify-hash
```

必须看到：

```text
ok: true
TIMEBASE_CONSISTENT: true
errors: []
```

如果出现：

- `capture_aborted`
- 窗口失焦/最小化
- video/session duration 偏差过大
- 目标大部分时间不可见

停止该 session，重新采集；不要用 proxy 或其他视频替代。

---

## 6. 采集完成后的处理

1. 四个新 session 都通过 `check_fps_pilot --verify-hash`；
2. 人工抽查目标覆盖和第一人称来源；
3. 用 old 模型跑 tiled C dry-run；
4. 重新提取 P0-C 特征；
5. 每类 3 个 session 后再做 H/B 描述统计；
6. 仍不训练分类器，直到 session 数和标签质量满足要求。

---

## 7. 当前不做

- 不扩到多地图；
- 不重训模型；
- 不启用 new 模型；
- 不将 1 个 H/B 结果外推为行为结论；
- 不使用新模型的高覆盖 body 结果替代 old。