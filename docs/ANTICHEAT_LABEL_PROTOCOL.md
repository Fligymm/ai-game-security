# 反作弊行为标签与威胁模型协议

版本：v1.0  
日期：2026-11-15  
状态：**P0-A approved; protocol only, no data collection started**  
批准：项目所有者，2026-11-15  
关联文档：

- [`ANTICHEAT_DEV_DRAFT.md`](ANTICHEAT_DEV_DRAFT.md)
- [`research/ACADEMIC_FEASIBILITY_REVIEW.md`](research/ACADEMIC_FEASIBILITY_REVIEW.md)
- [`ACADEMIC_USE_NOTICE.md`](ACADEMIC_USE_NOTICE.md)
- [`LEGAL_AND_ETHICS.md`](LEGAL_AND_ETHICS.md)

---

## 1. 目的

本协议固定反作弊行为研究的**标签语义、采集边界、威胁模型和不可比较项**，防止后续
把“CV Agent”“合成轨迹”“游戏 Bot”误写成“真实外挂”，也防止 proxy 数据被当作
FPS 反作弊准确率。

本协议只定义 P0-A 的研究规范，不包含采集、模型训练或代码实现。

---

## 2. 核心原则

1. **标签描述来源，不描述意图。**  
   一个 session 的标签来自它的采集来源/生成方式，而不是分类器输出，也不是研究者
   对“像不像作弊”的主观判断。
2. **CV Agent 不等于真实作弊。**  
   CV Agent 是受控视觉输入模拟器，只能作为“机器行为”研究对象；不能把它称为
   real cheat，也不能用它的检测结果宣称检测真实外挂。
3. **游戏 Bot 不等于外挂。**  
   游戏内置 Bot 是游戏 AI，是正常对照对象，不是作弊者。
4. **行为证据不等于意图证明。**  
   任何输出只能是“行为异常/风险信号”，不能单凭模型输出证明玩家作弊。
5. **没有合规的真实作弊样本，就不设 X 类结论。**  
   如果无法获得授权、隔离、合法的真实辅助瞄准样本，论文必须写“X not evaluated”。

---

## 3. 标签定义

### 3.1 四类对象

| 标签 | 含义 | 采集对象 | 可否称为“作弊” |
|---|---|---|---|
| `H` / `human` | 真实玩家在受控离线场景中的瞄准行为 | 自愿参与者 | 否 |
| `B` / `game_bot` | 游戏内置 Bot 或离线 Bot 的瞄准行为 | 游戏/离线 Bot | 否 |
| `C` / `cv_agent` | 仅基于屏幕视觉和输入模拟的受控 Agent | 本项目/受控 Agent | **否** |
| `X` / `real_cheat` | 真实辅助瞄准使用者或授权的真实外挂样本 | 仅在合法隔离条件下 | 是；但当前默认不采集 |

### 3.2 旧标签映射

现有数据中的旧标签只能按以下方式解释：

```text
human                    -> H（但当前是 2D 点击任务，不是 FPS）
bot_agent                -> B_proxy（直线匀速生成器，不是游戏 Bot）
synthetic_adversarial    -> C_proxy（合成轨迹，不是 CV Agent 实测）
```

`B_proxy` / `C_proxy` 只能用于工具开发和负结果对照，不能作为 P0 的最终 H/B/C 证据。

### 3.3 标签字段

每个 session 至少包含：

```json
{
  "agent_type": "human | game_bot | cv_agent | real_cheat",
  "agent_subtype": "free_text",
  "label_source": "capture | game_ai | generated | authorized_lab",
  "label_confidence": "certain | probable | unknown",
  "is_proxy": true,
  "session_group": "participant/bot/agent id",
  "map": "map or scene id",
  "scene": "static_target | strafe | peek | ...",
  "weapon": "weapon id or unknown"
}
```

规则：

- `agent_type` 是唯一主标签；
- `is_proxy=true` 的数据不得进入最终测试集；
- `label_source` 必须可追溯；
- 不允许用模型预测结果回填 `agent_type`。

---

## 4. 威胁模型

### 4.1 防御方视角

本研究只考虑**外部可观察信息**：

```text
屏幕帧
目标检测框
跟踪轨迹
时间戳
可选的鼠标/输入轨迹
```

不包含：

```text
进程内存
游戏内部状态
驱动/Hook
网络协议
服务器日志
反作弊 SDK
```

### 4.2 攻击者视角

潜在规避方式包括：

- 平滑/限制角速度；
- 随机延迟；
- 抖动/过冲/修正；
- 降低采样率；
- 模仿人类反应时间；
- 改变分辨率/帧率/压缩质量。

本研究不开发、不发布规避工具；只在受控数据上评估检测退化。

### 4.3 结论边界

模型输出只能支持：

- “该 session 的行为与 H/B/C 中某一类的参考分布更接近”；
- “存在需要人工复核的异常信号”。

不能支持：

- “该玩家一定作弊”；
- “该模型检测所有外挂”；
- “真实外挂检测准确率 X%”。

---

## 5. 采集边界

### 5.1 共同要求

- 只在离线/封闭环境采集；
- 不连接正式服务器，不使用真实账号；
- 不读取游戏内存，不注入，不修改游戏数据；
- 不绕过反作弊、DRM 或防截屏措施；
- 记录采集日期、地图、场景、分辨率、FPS、灵敏度、FOV、武器、设备；
- 原始数据不公开；发布前做隐私和版权审查；
- 所有 session 必须有不可变 manifest 和 SHA256。

### 5.2 H（human）

- 自愿参与者，事先说明用途；
- 不采集姓名、账号、聊天、语音等个人数据；
- 不采集未成年人数据；
- 记录自报游戏经验等级（新手/中级/高级），但经验等级不是作弊标签；
- 允许高手的快速甩枪、预瞄、跟枪；不得把“高水平”自动标成异常。

### 5.3 B（game_bot）

- 使用游戏内置 Bot 或离线 Bot；
- 固定难度/武器/地图，记录 Bot 配置；
- 不把 Bot 的机械直线行为当作“外挂样本”；
- 至少覆盖多个难度或移动模式（若可用）。

### 5.4 C（cv_agent）

- 只使用屏幕输入和受控输出；
- 记录 Agent 配置、检测阈值、跟踪器、控制策略；
- 不把 Agent 调参到“完美人类”后当作真实作弊；
- 必须与 H/B 在相同地图、场景、分辨率下采集。

### 5.5 X（real_cheat）

默认**不采集**。只有在以下条件全部满足时才允许：

- 有明确授权/合规依据；
- 隔离环境，不影响真实玩家；
- 不涉及真实账号、真实对局；
- 有数据保留和销毁计划；
- 法律/伦理评审通过。

没有 X 数据时，论文必须写“real_cheat not evaluated”，不得用 C 代替 X。

---

## 6. 数据模型

### 6.1 Session 元数据

在现有 schema 上新增：

```json
{
  "schema_version": "anticheat.session.v1",
  "session_id": "unique",
  "session_group": "participant/bot/agent id",
  "agent_type": "human",
  "agent_subtype": "free_text",
  "label_source": "capture",
  "label_confidence": "certain",
  "is_proxy": false,
  "game": "cs2_offline",
  "map": "map_id",
  "scene": "scene_id",
  "weapon": "weapon_id",
  "sensitivity": 2.0,
  "fov": 90,
  "resolution": "1920x1080",
  "capture_fps": 120,
  "input_device": "mouse",
  "collected_at": "2026-11-15T00:00:00+08:00",
  "operator_id": "anonymous",
  "manifest_sha256": "..."
}
```

### 6.2 时间序列

```json
{
  "timestamps": [0.0, 0.0083],
  "x": [0.0, 1.0],
  "y": [0.0, 1.0],
  "dx": [0, 1],
  "dy": [0, 1]
}
```

可选字段：

```text
camera_yaw, camera_pitch
target_track_ids
screen_target_x, screen_target_y
input_buttons
```

### 6.3 事件

```json
{"phase": "target_appear", "start_idx": 0, "end_idx": 1}
{"phase": "reaction_phase", "start_idx": 1, "end_idx": 5}
{"phase": "target_acquisition", "start_idx": 5, "end_idx": 30}
{"phase": "tracking", "start_idx": 30, "end_idx": 80}
```

事件由人工/规则标注，必须有 `label_source` 和审核状态；不能由分类器自行回填。

### 6.4 视觉对齐

P0-C 需要新增：

```json
{
  "video_id": "session_id",
  "frame_range": [0, 600],
  "track_id": 7,
  "input_session_id": "session_id",
  "alignment_error_ms": 8.0
}
```

没有对齐字段的数据不能用于“视觉行为”结论。

---

## 7. 标注规则

### 7.1 决策树

```text
该轨迹是否来自真实玩家？
  是 -> H
  否 -> 是否来自游戏 AI/Bot？
          是 -> B
          否 -> 是否由受控视觉 Agent 生成/执行？
                  是 -> C
                  否 -> 是否来自授权的真实辅助瞄准样本？
                          是 -> X
                          否 -> 不纳入最终数据集
```

### 7.2 禁止规则

- 不按“像不像作弊”打 H/X 标签；
- 不把 C 标成 X；
- 不把 B 标成 X；
- 不把 proxy 标成 `is_proxy=false`；
- 不用同一录像切帧制造多个独立 session；
- 不在 train/test 之间共享 `session_group` 或同一录像。

---

## 8. 纳入与排除

### 8.1 纳入

- 独立 session，时长 ≥ 5 秒或 ≥ 300 个采样点（以先到者为准）；
- 包含至少一次目标出现和一次瞄准/点击事件；
- 目标在画面内可见，且能人工确认；
- 时间戳严格递增；
- 元数据完整；
- 有 session manifest。

### 8.2 排除

- 采集中断、丢帧严重、时间戳异常；
- 目标不可见/被 UI 遮挡；
- 仅有静态画面、无瞄准行为；
- 无法确定来源（H/B/C/X）；
- 同一录像切出的重复 session；
- 含个人身份信息且无法脱敏。

排除原因必须记录，不得静默丢弃。

---

## 9. 质量控制和审核

### 9.1 Pilot

P0-B 先做 2–3 个 session 的 pilot：

- 验证帧/输入时间同步；
- 验证目标可见性和事件标注；
- 验证地图/场景/武器元数据；
- 验证 manifest 和脱敏；
- 通过后再扩大采集。

### 9.2 双人审核

至少 20% session 由第二人复核：

- `agent_type` 是否正确；
- 事件边界是否合理；
- 是否存在个人数据；
- 是否 proxy 混入。

不一致时保留原始记录，记录分歧和裁决理由。

### 9.3 自动校验

每个 session 必须通过：

- 长度一致；
- 时间戳严格递增；
- `dx/dy` 与位置差分一致（±1 px）；
- 事件范围合法；
- `agent_type` 合法；
- `is_proxy` 与来源一致；
- manifest 哈希存在。

---

## 10. 切分与泄漏控制

### 10.1 分组

```text
primary group   session_group（参与者/Bot/Agent 实例）
secondary group map/scene
```

- train/val/test 不得共享 `session_group`；
- 同一录像的窗口不得跨集合；
- 测试集不得用于调参或特征选择；
- H/B/C 在 train/val/test 中尽量分层。

### 10.2 推荐比例

```text
train 60% / val 20% / test 20%
```

样本不足时使用 grouped cross-validation，并报告每折结果；不要用随机窗口切分。

### 10.3 不可比较项

以下差异必须记录并在分析中分层，不能直接合并：

- 不同地图/场景；
- 不同分辨率/FPS/压缩；
- 不同灵敏度/FOV；
- 不同输入设备；
- 不同游戏版本/Bot 难度/Agent 配置；
- 不同玩家技能水平。

---

## 11. 指标与可声明结论

### 11.1 允许

- H vs B；
- H vs C；
- H vs B vs C（多分类）；
- X 单独报告（若有合规样本）；
- 跨 session/map 的泛化；
- 固定 FPR 下的 TPR；
- 校准和置信区间。

### 11.2 禁止

- 用 C 的结果宣称检测 real cheat；
- 用 proxy 数据宣称 FPS 泛化；
- 只报 accuracy；
- 只报 AUC 不报 FPR/PR；
- 把目标检测 mAP 当作反作弊准确率。

### 11.3 推荐报告

```text
ROC-AUC, PR-AUC
TPR @ FPR=1%
FPR @ TPR=95%
Brier / ECE
bootstrap 95% CI
per-class / per-map / per-scene
detection latency
```

---

## 12. 隐私、伦理与法律

- 遵守 [`ACADEMIC_USE_NOTICE.md`](ACADEMIC_USE_NOTICE.md) 和
  [`LEGAL_AND_ETHICS.md`](LEGAL_AND_ETHICS.md)；
- 不采集真实账号、聊天、语音、姓名；
- 不采集未成年人；
- 原始视频/轨迹不公开；
- 数据保留期限和销毁方式在采集前确定；
- 真实作弊样本（X）必须有单独授权，不能默认采集；
- 论文只报告聚合结果和脱敏示例，不发布可复现的攻击工具。

---

## 13. P0-A 验收

- [x] 四类标签 H/B/C/X 定义完成。
- [x] 旧 proxy 标签映射完成。
- [x] 采集边界与排除条件完成。
- [x] 数据 schema 字段完成。
- [x] 切分/泄漏控制规则完成。
- [x] 可声明/不可声明结论完成。
- [x] 隐私伦理边界完成。
- [ ] P0-B pilot 采集脚本和 2–3 个 session 验证（下一阶段）。

**P0-A 结论：协议已批准，可进入 P0-B pilot；尚未采集数据、未训练模型、未修改代码。**

---

## 14. 变更控制

- 任何标签语义变更必须更新本文件版本号；
- 任何新数据源必须记录 `label_source` 和 `is_proxy`；
- 任何测试集使用必须记录一次性和理由；
- 如果获得 X 数据，必须单独评审，不得直接混入 H/B/C 训练集；
- 本协议不替代法律意见；涉及真实玩家/真实作弊样本时需额外合规审查。