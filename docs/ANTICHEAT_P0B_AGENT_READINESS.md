# P0-B-R2：Game Bot / CV Agent 实验入口核查

日期：2026-11-15  
类型：只读代码与实验入口审查  
状态：**H/B pilot 已采集并通过 timebase 校验；C 离线 dry-run 已跑通；但检测覆盖偏低，行为学结论未验证**  
关联：

- [`ANTICHEAT_LABEL_PROTOCOL.md`](ANTICHEAT_LABEL_PROTOCOL.md)
- [`ANTICHEAT_P0B_PILOT.md`](ANTICHEAT_P0B_PILOT.md)
- [`ANTICHEAT_P0B_CAPTURE_REVIEW.md`](ANTICHEAT_P0B_CAPTURE_REVIEW.md)

> 本报告不启动游戏、不运行 `RealtimeAimLoop`/`run_real.py`、不发送输入、不生成实验数据。
> 结论只基于源码、CLI 和现有文档。

---

## 1. 总体结论

**P0-B 已从“桌面录屏”升级为“指定游戏窗口 + 生命周期 + 离线 CV dry-run”，但仍没有统一的三类 Agent 启动系统。**

| 对象 | 实际状态 | 能否直接产出 P0-B 数据 |
|---|---|---|
| Human | 采集工具存在；人类游戏行为需手动开始 | 需要真人 + CS2 离线环境 |
| Game Bot | 项目**没有自研 CS2 Game Bot**；只有离线轨迹生成器 | 只能用 CS2 内置 Bot，项目无启动入口 |
| CV Agent | 实时链路 + 离线 dry-run 工具存在 | 代码可运行，但本轮未执行/未验证采集 |
| P0-B capture | 抓指定窗口 + 生命周期 + 校验 | 不能启动/识别/同步 Agent |

**核心结论：**

> 目前可以准备 H/B screen-only POV pilot，也可以在已校验 H/B 视频上做 C dry-run；
> 但 Game Bot 没有项目级实现，CV Agent 真实运行与采集同步仍未验证。
> 因此**不能宣称已经具备完整的三类 Agent 实验能力**。

---

## 2. Human 实现状态及操作流程

### 2.1 状态

| 项目 | 状态 |
|---|---|
| Human Agent 代码 | **NOT IMPLEMENTED**（人类不由项目启动） |
| Human 采集工具 | **CODE EXISTS**：`tools/capture_fps_pilot.py` |
| 旧人工轨迹工具 | `tools/capture_human.py` 存在，但只是 **tkinter 2D 点击任务**，不是 FPS |
| ENTRYPOINT EXISTS | **YES（仅采集入口）** |
| CAN RUN OFFLINE | **PARTIAL**：需 CS2 离线环境和真人，本轮未验证 |
| DATA CAPTURE VERIFIED | **NO** |

### 2.2 如何启动

Human session 需要两个独立步骤：

1. **人工启动 CS2 离线场景**（本地/离线地图，不登录正式服务器）；
2. 在人开始操作前后，运行采集工具：

```powershell
.\.venv\Scripts\python.exe tools\capture_fps_pilot.py `
  --agent-type human `
  --capture-source player_pov `
  --view-mode first_person `
  --scene static_target `
  --map-name aim_botz `
  --weapon ak47 `
  --sensitivity 0.8 `
  --fov 90 `
  --duration 180 `
  --operator-id anon_h01 `
  
  --output-dir runs\captures\p0b_pilot `
  --attest-pov `
  --attest-experiment `
  --confirm-offline
```

采集工具不会启动 CS2、不会发送输入、不会控制人类玩家。

### 2.3 参与者识别

- `--operator-id` 只是**自报的匿名标签**；
- 没有身份认证、摄像头、账号校验或知情同意校验；
- `check_fps_pilot.py` 只能检查该字段是否存在，不能验证“确实由某位人类操作”；
- 当前没有“参与者 ID 与 session 一一对应”的登记表。

### 2.4 是否需要额外配置

需要：

- 真人参与者（成年人、知情同意、匿名 ID）；
- CS2 离线环境；
- 第一人称玩家视角；
- 保持窗口前台、可见、未最小化；
- 统一分辨率/FOV/灵敏度；
- 采集前确认画面中没有账号/聊天/玩家名。

不需要：

- 项目级 Human Agent；
- 按键/鼠标 hook；
- 真实控制后端。

**结论：Human 侧可以准备，但“实际采集通过”尚未发生。**

---

## 3. Game Bot 实现状态及操作流程

### 3.1 状态

| 项目 | 状态 |
|---|---|
| 自研 CS2 Game Bot | **NOT IMPLEMENTED** |
| 轨迹生成器 | `MechanicalBotAgent`、`SyntheticAgent` 存在，但只是离线轨迹生成 |
| 项目级 Game Bot 启动入口 | **NO** |
| 能否在 CS2 中独立运行 | **NO**（项目代码不驱动 CS2 Bot） |
| 能否产生可观察/可记录行为 | 只能用 CS2 自身 Bot；项目不控制 |
| DATA CAPTURE VERIFIED | **NO** |

### 3.2 两个“Bot”不要混淆

| 名称 | 实际是什么 | 是否 Game Bot |
|---|---|---|
| `MechanicalBotAgent` | 从起点到终点的直线匀速轨迹生成器 | **否** |
| `SyntheticAgent` | 带反应、修正、抖动、pause 的合成轨迹生成器 | **否** |
| CS2 内置 Bot | 游戏 AI | 是，但不是项目实现 |

`MechanicalBotAgent` 和 `SyntheticAgent` 不连接游戏、不驱动角色、不产生游戏画面，
只能作为离线 proxy 轨迹，不能当作 P0-B 的 Game Bot 数据。

### 3.3 可执行流程

项目没有 `bot_add`、Bot 配置或启动脚本。若要用 **CS2 内置 Bot** 做 B session：

1. 人工启动 CS2 离线地图；
2. 在游戏内启动/配置内置 Bot；
3. 进入观察者模式，选择目标 Bot；
4. 切换到该 Bot 的**第一人称视角**；
5. 确认不是第三人称/自由视角；
6. 运行采集工具，显式填写 `observer_followed_bot`：

```powershell
.\.venv\Scripts\python.exe tools\capture_fps_pilot.py `
  --agent-type game_bot `
  --capture-source observer_followed_bot `
  --view-mode first_person `
  --scene static_target `
  --map-name aim_botz `
  --weapon ak47 `
  --sensitivity 0.8 `
  --fov 90 `
  --duration 180 `
  --operator-id anon_b01 `
  
  --output-dir runs\captures\p0b_pilot `
  --attest-pov `
  --attest-experiment `
  --confirm-offline
```

注意：

- 采集工具**不会启动 Bot**；
- 项目没有验证 Bot 是否真的在运行；
- `agent_type=game_bot` 和 `capture_source=observer_followed_bot` 是人工标签；
- 如果无法稳定跟随第一人称，应停止 session，不得降级为第三人称。

---

## 4. CV Agent 实现状态及操作流程

### 4.1 实时链路

| 项目 | 状态 |
|---|---|
| 完整 CV Agent | **CODE EXISTS**：`AimPipeline` + `RealtimeAimLoop` |
| 感知模块 | `YOLODetector` 存在 |
| 决策/选择 | 目标转换、`TargetSelector`、Kalman、轨迹规划存在 |
| 执行模块 | `AimController` + 后端存在 |
| 真实控制入口 | `run_real.py` 存在 |
| 干运行入口 | `python -m vision.stream.realtime_loop` 存在 |
| CAN RUN OFFLINE | **PARTIAL**：代码支持，本轮未执行、未验证 |
| DATA CAPTURE VERIFIED | **NO** |

### 4.2 这不是“只有检测器”

`AimPipeline` 的实际链路是：

```text
frame
 -> YOLODetector
 -> detections_to_states
 -> TargetSelector
 -> Kalman / prediction
 -> trajectory planning
 -> AimController
 -> CSV / 可选真实后端
```

所以它是**完整闭环原型**，不是只有 YOLO 检测。

### 4.3 实时干运行入口（不发送真实输入）

```powershell
.\.venv\Scripts\python.exe -m vision.stream.realtime_loop `
  --weights runs\detect\cs2_multitarget_ft_v1\weights\best.onnx `
  --backend csv `
  --record-dir runs\captures\p0b_cv_dry `
  --record-source cv_agent `
  --record-scene static_target `
  --frames 600 `
  --no-hotkeys `
  --no-overlay
```

性质：

- 会运行检测/选择/轨迹规划；
- `--backend csv` 不发送真实鼠标；
- 仍需要屏幕中有 CS2 画面；
- **没有真实瞄准输出**，所以它不是“正在执行辅助瞄准的 CV Agent 行为”；
- 可以作为感知/决策链路的技术验证，但不能直接当作 C 类行为数据。

### 4.4 离线 dry-run 入口（推荐用于 C）

[`tools/run_cv_agent_offline.py`](../tools/run_cv_agent_offline.py)

- 只接受已通过 `check_fps_pilot --verify-hash` 的 H/B session；
- 读取原始 `capture.mp4`，不修改；
- 复用 `TiledDetector -> AimPipeline -> CSVLoggerBackend`；
- 默认 3×3、tile 720，解决 320 ROI 模型直接跑 1920×1080 的小目标漏检；
- 强制 `apply_mouse=False`；
- 不启动 `run_real.py`，不发送游戏输入；
- 输出逐帧 JSONL、决策 CSV、源视频/模型哈希。

验证状态：已在**真实 H/B pilot 视频**上完成 dry-run（`dry_run=true`、
`real_control=false`、source session/video SHA 关联、`capture_time_s` 来自 events）；
使用 3×3 tiling 后 H 759/1604 帧、B 1124/1641 帧有检测，671/908 帧选中并写入 CSV。
行为学结论仍未验证。

```powershell
.\.venv\Scripts\python.exe tools\run_cv_agent_offline.py `
  "runs\captures\p0b_pilot\<verified-session>" `
  --output-dir runs\eval\anticheat_cv_offline\<source-session> `
  --model runs\detect\cs2_detection_v2\weights\best.onnx `
  --conf 0.35 `
  --iou 0.5
```

### 4.5 真实 CV Agent 入口（本轮禁止执行）

```powershell
python run_real.py `
  --record-dir runs\captures\p0b_pilot `
  --record-source cv_agent `
  --record-scene static_target `
  --record-operator-id agent01 `
  --frames 600
```

该脚本会注入真实 Win32 鼠标后端并自动追加 `--backend win32` 和 `--apply-mouse`。

**本报告未执行该命令，也不建议在未确认 kill switch、离线环境和人工监督时执行。**

---

## 5. P0-B 采集工具实际能力边界

`tools/capture_fps_pilot.py` 仍不是 Agent 启动器。

| 问题 | 实际答案 |
|---|---|
| `--agent-type` 只是元数据吗？ | **是**；同时 `--capture-source`/`--view-mode` 也是显式人工字段 |
| 是否启动任何 Agent？ | **否**；只启动 `WindowCapture` |
| 是否读取 Agent 行为输出？ | **否**；`detections=()`、`selected=None`、`applied_mouse=False` |
| `events.jsonl` 记录什么？ | 每帧空检测、无选中、无鼠标 delta、`pilot/frame_index` |
| 是否捕获原始鼠标/键盘输入？ | **否** |
| 是否保证视频与 Agent 同一次实验？ | **仅靠人工流程**；没有 start/stop marker 与 Agent 进程绑定 |
| 是否验证“确实是 H/B”？ | **否**；只校验显式字段和人工 attestation |
| 是否抓指定窗口？ | **是**：`WindowCapture` 查 CS2 窗口客户端区域 |
| 窗口失效怎么办？ | **fail-closed**：失焦/最小化/尺寸变化/窗口消失就中止 |
| `check_fps_pilot --verify-hash` 证明什么？ | 文件完整性和视频可解码；**不证明 Agent 身份** |

### 5.1 窗口采集

[`vision/stream/window_capture.py`](../vision/stream/window_capture.py)：

- `EnumWindows` 默认按 **`cs2.exe` 进程**识别窗口，不依赖本地化标题；
  中文标题 `反恐精英：全球攻势` 也可匹配；
- `GetClientRect` + `ClientToScreen` 获取客户端区域；
- 每帧校验窗口仍存在、可见、未最小化、前台、尺寸不变；
- 使用 `mss` 抓取该区域；
- 默认 `--focus-window` 把 CS2 切到前台；终端失焦是正常的；
- 不降级为桌面抓屏。

限制：

- 独占全屏/HDR/受保护内容可能失败；
- 窗口遮挡/失焦会拒绝；
- 不保证所有 CS2 显示模式；需要实际桌面验证。

### 5.2 生命周期

`lifecycle.jsonl` 记录：

```text
session_created
game_window_verified
capture_started
experiment_started
experiment_finished
capture_stopped
manifest_generated
video_artifact
integrity_verified
```

异常时写 `capture_aborted`，不伪造 `experiment_finished`。

### 5.3 校验状态

`check_fps_pilot` 返回独立状态：

```text
FILE_INTEGRITY_VERIFIED
VIDEO_DECODE_VERIFIED
GAME_WINDOW_OBSERVED
POV_MANUALLY_ATTESTED
EXPERIMENT_MANUALLY_ATTESTED
TIMEBASE_CONSISTENT
```

这些状态不可互相替代。

---

## 6. 三种 session 的可执行性矩阵

图例：**YES** = 已存在且可用；**PARTIAL** = 部分存在/需人工；**NO** = 不存在/未验证。

| 对象 | CODE EXISTS | ENTRYPOINT EXISTS | CAN RUN OFFLINE | DATA CAPTURE VERIFIED |
|---|---|---|---|---|
| Human | YES（采集工具） | YES（采集入口；人工启动游戏） | PARTIAL（需真人+CS2） | **NO** |
| Game Bot | PARTIAL（仅离线轨迹生成器） | **NO**（项目无 Bot 启动入口） | **NO**（项目不驱动 CS2） | **NO** |
| CV Agent | YES（实时 + 离线工具） | YES（`run_real.py`；`run_cv_agent_offline.py`） | PARTIAL（代码可运行，本轮未执行） | **NO** |
| P0-B 采集工具 | YES | YES | PARTIAL（需窗口） | **NO** |

### 6.1 关键区分

- **代码存在 ≠ 入口存在**：`MechanicalBotAgent` 有类，但不是 Game Bot 入口。
- **入口存在 ≠ 能离线运行**：`run_real.py` 能启动，但本报告未执行，且它走真实控制。
- **能运行 ≠ 采集有效**：`capture_fps_pilot` 抓窗口，但不启动/同步 Agent。
- **`check_fps_pilot` 通过 ≠ 数据真实**：它只检查元数据、文件、视频和人工 attestation。

---

## 7. 当前阻塞及最小后续任务

| 阻塞 | 影响 | 最小后续任务 | 是否需要改代码 |
|---|---|---|---|
| 当前已发现 CS2 窗口，但无真人参与者/H/B session | 无法完成有效 H/B 采集 | 安排真人并在离线桌面执行 pilot | 否 |
| 当前无真人参与者 | 无法采集 H | 安排匿名成年参与者 | 否 |
| 无自研 Game Bot/启动器 | B session 只能手动用 CS2 Bot | 先手动用 CS2 内置 Bot；若要自动化，另行评审 | 后续可能需要 |
| `run_real.py` 是真实控制入口 | 不能在本轮执行 | 由项目所有者在监督下运行；保持 kill switch | 否 |
| capture 不启动 Agent | 视频-行为对应靠人工 | 增加 start/stop marker 或统一实验脚本（后续） | 后续需要 |
| `agent_type`/`capture_source` 是人工标签 | 无法自动证明 H/B | 人工记录 + 双人复核 + 采集清单 | 否 |
| 无输入轨迹 | 只能做 screen-only 分析 | 先接受 screen-only；输入轨迹另行评审 | 后续可能需要 |

### 7.1 当前可执行的最小实验

只在具备条件的桌面上：

1. 人工启动 CS2 离线场景；
2. 运行 `capture_fps_pilot.py` 录 H；
3. 用 CS2 内置 Bot + 观察者第一人称录 B；
4. 用 `check_fps_pilot.py --verify-hash` 校验；
5. 用 `run_cv_agent_offline.py` 对已校验 H/B 做 C dry-run。

### 7.2 当前不能执行的实验

- 自动启动/停止 Game Bot；
- 自动启动/停止 CV Agent 并与采集工具同步；
- 用 `capture_fps_pilot` 读取 Agent 的检测/决策结果；
- 采集原始鼠标/键盘输入；
- 证明视频确实由某个 Agent 产生；
- 当前无真人参与者/完整 H/B session 的真实采集。

---

## 8. 是否具备开展真实 P0-B 实验的条件

### 结论

**不完全具备。**

- **Human：** 采集工具和流程具备，只缺真实参与者/游戏桌面；可以准备，但不等于已验证。
- **Game Bot：** 项目没有自研 Game Bot；只能用 CS2 内置 Bot 手动完成 B session。
- **CV Agent：** 实时链路和离线 dry-run 工具存在；真实运行涉及真实控制，本轮未执行。
- **P0-B 采集工具：** 已能抓指定窗口并 fail-closed，但不启动 Agent、不读取 Agent 输出、不捕获输入。

### 状态判定

```text
Human        CODE EXISTS / ENTRYPOINT EXISTS / CAN RUN OFFLINE PARTIAL / DATA CAPTURE VERIFIED NO
Game Bot     CODE EXISTS (trajectory generators only) / ENTRYPOINT NO / CAN RUN OFFLINE NO / DATA CAPTURE VERIFIED NO
CV Agent     CODE EXISTS / ENTRYPOINT EXISTS / CAN RUN OFFLINE PARTIAL / DATA CAPTURE VERIFIED NO
P0-B tool    CODE EXISTS / ENTRYPOINT EXISTS / CAN RUN OFFLINE PARTIAL / DATA CAPTURE VERIFIED NO
```

### 最终建议

1. **先做 Human + CS2 内置 Bot 的 screen-only pilot**，确认窗口采集、POV、标签和校验流程。
2. **CV Agent 只允许在项目所有者监督下用 `run_real.py` 显式启动**；本报告不执行。
3. C 实验优先用 `run_cv_agent_offline.py` 对已校验 H/B 做 dry-run，而不是实时控制。
4. 在真实 H/B 数据通过校验前，不使用 proxy 数据、桌面录屏或合成轨迹替代 P0-B 结论。

---

## 附录：准确命令清单

### Human

```powershell
.\.venv\Scripts\python.exe tools\capture_fps_pilot.py `
  --agent-type human --capture-source player_pov --view-mode first_person `
  --scene static_target --map-name aim_botz --weapon ak47 `
  --sensitivity 0.8 --fov 90 --duration 180 `
  --operator-id anon_h01 `
  --output-dir runs\captures\p0b_pilot `
  --attest-pov --attest-experiment --confirm-offline
```

### Game Bot（项目无入口；需先手动启动 CS2 Bot）

```powershell
.\.venv\Scripts\python.exe tools\capture_fps_pilot.py `
  --agent-type game_bot --capture-source observer_followed_bot `
  --view-mode first_person --scene static_target --map-name aim_botz `
  --weapon ak47 --sensitivity 0.8 --fov 90 --duration 180 `
  --operator-id anon_b01 `
  --output-dir runs\captures\p0b_pilot `
  --attest-pov --attest-experiment --confirm-offline
```

### CV Agent 离线 dry-run

```powershell
.\.venv\Scripts\python.exe tools\run_cv_agent_offline.py `
  "runs\captures\p0b_pilot\<verified-session>" `
  --output-dir runs\eval\anticheat_cv_offline\<source-session> `
  --model runs\detect\cs2_detection_v2\weights\best.onnx
```

默认模型已回退 old；new 仅作显式对比候选。

### CV Agent 实时 dry-run（不是真实 C 行为）

```powershell
.\.venv\Scripts\python.exe -m vision.stream.realtime_loop `
  --weights runs\detect\cs2_multitarget_ft_v1\weights\best.onnx `
  --backend csv --record-dir runs\captures\p0b_cv_dry `
  --record-source cv_agent --record-scene static_target --frames 600 `
  --no-hotkeys --no-overlay
```

### 校验

```powershell
$session = Get-ChildItem runs\captures\p0b_pilot -Directory |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1
.\.venv\Scripts\python.exe tools\check_fps_pilot.py $session.FullName --verify-hash
```

`--verify-hash` 只验证文件哈希和视频解码，不验证 Agent 身份或实验真实性。