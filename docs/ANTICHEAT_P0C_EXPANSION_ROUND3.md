# P0-C 第三轮扩样：5H/5B -> 10H/10B

日期：2026-11-16  
状态：**数据已采集，但 6 个新 H 地图与 B 不一致；该批不能用于 H/B 分类**
> 见 [`P0C_MAP_CONFOUND.md`](research/P0C_MAP_CONFOUND.md)。
> 需要补 5 个旧地图 H，而不是继续补 B。

## 为什么采

Feature v2 首轮 5H/5B：

```text
F2 tracking only:
  RandomForest   accuracy 0.80, AUC 0.92
  Logistic       accuracy 0.80, AUC 0.84

其他特征族单独接近 chance
全部特征混用后 RF AUC 回落到 0.80
```

F2 是条件性 pilot 信号。需要独立 10H/10B 验证，且新 session 不参与特征选择。

## 目标

当前：

```text
H = 5
B = 5
```

新增：

| Session | 类型 | operator_id |
|---|---|---|
| H-06 | human / player_pov | `anon_h06` |
| H-07 | human / player_pov | `anon_h07` |
| H-08 | human / player_pov | `anon_h08` |
| H-09 | human / player_pov | `anon_h09` |
| H-10 | human / player_pov | `anon_h10` |
| B-06 | game_bot / observer_followed_bot | `anon_b06` |
| B-07 | game_bot / observer_followed_bot | `anon_b07` |
| B-08 | game_bot / observer_followed_bot | `anon_b08` |
| B-09 | game_bot / observer_followed_bot | `anon_b09` |
| B-10 | game_bot / observer_followed_bot | `anon_b10` |

达到每类 10 个独立 session。

## 采集要求

```text
时长            60 秒
分辨率          1920×1080
FPS             30
地图            aim_botz
场景            static_target
武器            ak47
灵敏度          0.8
FOV             90
视角            first_person
模型            old default
```

必须：

- 每个 session 独立启动；
- 不复用同一录像切帧；
- H：真实玩家正常操作，最好有至少 2 位不同参与者；
- B：CS2 内置 Bot + 观察者第一人称，最好变化 Bot 配置/位置；
- 采集期间游戏窗口保持前台，不点回终端；
- B 无法稳定跟随第一人称时停止，不降级为第三人称；
- 不采集账号、聊天、语音、玩家名；
- 不使用 proxy、合成轨迹、桌面录屏。

## 采集脚本

[`scripts/capture_p0b_expansion.ps1`](../scripts/capture_p0b_expansion.ps1)

脚本只录屏，不启动游戏、不启动 Agent、不发送输入；采集后自动执行
`check_fps_pilot.py --verify-hash`。

### H（依次执行，编号改到 h06–h10）

先启动 CS2 离线地图并保持第一人称：

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human `
  -CaptureSource player_pov `
  -OperatorId anon_h06
```

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human `
  -CaptureSource player_pov `
  -OperatorId anon_h07
```

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human `
  -CaptureSource player_pov `
  -OperatorId anon_h08
```

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human `
  -CaptureSource player_pov `
  -OperatorId anon_h09
```

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType human `
  -CaptureSource player_pov `
  -OperatorId anon_h10
```

### B（依次执行，编号改到 b06–b10）

每次先手动进入观察者模式、选择 CS2 内置 Bot、切到 Bot 第一人称，然后：

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType game_bot `
  -CaptureSource observer_followed_bot `
  -OperatorId anon_b06
```

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType game_bot `
  -CaptureSource observer_followed_bot `
  -OperatorId anon_b07
```

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType game_bot `
  -CaptureSource observer_followed_bot `
  -OperatorId anon_b08
```

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType game_bot `
  -CaptureSource observer_followed_bot `
  -OperatorId anon_b09
```

```powershell
.\scripts\capture_p0b_expansion.ps1 `
  -AgentType game_bot `
  -CaptureSource observer_followed_bot `
  -OperatorId anon_b10
```

## 校验

脚本已自动校验。也可以手动：

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

失败就重录；aborted session 保留但不要使用。

## 完成后

告诉我，我会：

1. 校验 10 个新 session；
2. old 模型 tiled C；
3. 固定 F2 特征，不重新做特征选择；
4. 10H/10B leave-one-session-out；
5. 根据结果决定论文级实验或停止。

仍不训练正式分类器，不改默认模型，不发布权重。