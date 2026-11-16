# P0-C 第二轮扩样：3H/3B -> 5H/5B

日期：2026-11-16  
状态：**已完成 5H/5B；B-04 由 `p0b_game_bot_20261116_214446` 补录；baseline 完成但不支持可靠分类**

当前结果：

```text
H-04  p0b_human_20261116_213610    ok=true / timebase=true
H-05  p0b_human_20261116_213729    ok=true / timebase=true
B-04  p0b_game_bot_20261116_213851 capture_aborted: game window lost foreground
B-05  p0b_game_bot_20261116_214003 ok=true / timebase=true
```

B-04 已由 `p0b_game_bot_20261116_214446` 补录并通过校验。当前有效为 **5H / 5B**。

5H/5B 特征和 baseline：

- [`P0C_5X5_FEATURES.md`](research/P0C_5X5_FEATURES.md)
- Logistic / RF 均 6/10；AUC 0.68 / 0.72；仍不支持可靠分类。

## 原因

3H/3B leave-one-session-out baseline 结果：

```text
Dummy majority        accuracy 0.500
LogisticRegression    accuracy 0.667, AUC 0.556
RandomForest depth=2  accuracy 0.333, AUC 0.222
```

当前 6 个 session 不足以支持可靠分类。下一步应优先增加**独立 session**，
而不是继续调参或换模型。

## 目标

在当前 3H/3B 基础上，再增加：

| Session | 类型 | operator_id |
|---|---|---|
| H-04 | human / player_pov | `anon_h04` |
| H-05 | human / player_pov | `anon_h05` |
| B-04 | game_bot / observer_followed_bot | `anon_b04` |
| B-05 | game_bot / observer_followed_bot | `anon_b05` |

达到每类 5 个 session。

要求：

- 同 map/scene/weapon/FOV/sensitivity；
- 独立启动；
- 60s；
- first-person；
- old 模型默认；
- 不复用同一录像切帧；
- B 只使用 CS2 内置 Bot + 观察者第一人称。

## 推荐脚本

[`scripts/capture_p0b_expansion.ps1`](../scripts/capture_p0b_expansion.ps1)

它会调用采集工具、强制 attestation，并自动执行
`check_fps_pilot.py --verify-hash`。

### H-04

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human `
  -CaptureSource player_pov `
  -OperatorId anon_h04
```

### H-05

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human `
  -CaptureSource player_pov `
  -OperatorId anon_h05
```

### B-04

先手动进入观察者模式并跟随 Bot 第一人称，再运行：

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType game_bot `
  -CaptureSource observer_followed_bot `
  -OperatorId anon_b04
```

### B-05

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType game_bot `
  -CaptureSource observer_followed_bot `
  -OperatorId anon_b05
```

### B-04 补录（替代 aborted session）

B-04 在 55.6 秒时因游戏窗口失焦被 fail-closed 中止，不能使用。请重新进入
观察者第一人称后运行：

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType game_bot `
  -CaptureSource observer_followed_bot `
  -OperatorId anon_b04b
```

采集期间不要点回终端或切换窗口。

## 采集后

脚本会自动运行校验；必须看到：

```text
ok: true
TIMEBASE_CONSISTENT: true
errors: []
```

采集完成后告诉我，我会：

1. 校验 4 个新 session；
2. 用 old 模型跑 tiled C；
3. 重跑 P0-C 特征；
4. 做 5H/5B leave-one-session-out baseline；
5. 仍不训练正式分类器，除非样本量和结果支持。

## 当前不做

- 不在 6 个 session 上继续调参；
- 不重新启用 new 模型；
- 不修改冻结模型；
- 不发布权重；
- 不使用 proxy 数据。