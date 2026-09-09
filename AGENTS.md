# AGENTS.md - Codex Agent 行为约束配置

> 本文件定义了所有 Codex agents 在此项目中必须遵守的强制规则

## 项目信息
- **项目名**：AI Game Security Lab
- **模块**：AI-driven game anti-cheat & behavior analysis
- **关键系统**：Vision → Detection → Control Pipeline（`cv_agent.control`）

---

## Agent 禁止操作清单

### 🔴 Level 1：严格禁止（会导致 PR 拒绝）

#### 控制流相关
1. **不允许硬编码 `apply_mouse=False`**
   - 文件：`vision/stream/realtime_loop.py`、`cv_agent/orchestrator.py`
   - 原因：破坏用户的动态控制能力
   - 后果：代码审查拒绝

2. **不允许删除或重命名 `ChainedBackend` 类**
   - 文件：`cv_agent/control/backends/chained.py`
   - 原因：这是多后端链式架构的核心
   - 后果：无法同时进行 CSV 记录 + 真实控制

3. **不允许移除 `CSVLoggerBackend` 的 `flush()` 调用**
   - 影响文件：`cv_agent/control/backends/csv_logger.py`
   - 原因：确保日志实时写入，防止数据丢失
   - 后果：轨迹数据可能丢失

4. **不允许移除全局 Kill Switch（ESC/F12）**
   - 文件：`vision/stream/safety.py`、`vision/stream/realtime_loop.py`
   - 原因：紧急安全机制，防止失控
   - 后果：安全隐患 + PR 拒绝

#### 后端相关
5. **不允许强制 `dry_run=True` 在 Win32APIBackend 中**
   - 文件：`cv_agent/control/backends/win32.py`
   - 原因：Hook 机制需要能够注入 `dry_run=False`
   - 后果：真实驱动注入失败

6. **不允许删除 `custom_handler` 参数**
   - 文件：`cv_agent/control/backends/win32.py`、`cv_agent/control/factory.py`
   - 原因：`run_real.py` 的 Hook 机制依赖此参数
   - 后果：无法通过 Hook 注入真实驱动

#### 命令行相关
7. **不允许移除 `--apply-mouse` 参数**
   - 文件：`vision/stream/realtime_loop.py` 的 main 块
   - 原因：用户显式控制真实控制的唯一方式
   - 后果：用户无法启用真实控制

8. **不允许将 `--apply-mouse` 默认值改为 `True`**
   - 文件：`vision/stream/realtime_loop.py` 的 RealtimeLoopConfig
   - 原因：默认必须是安全的干运行模式
   - 后果：意外启用真实控制

---

### 🟡 Level 2：强烈不建议（可能导致功能缺陷）

1. **不建议删除 `log_only()` 方法**
   - 文件：`cv_agent/control/mouse.py`
   - 原因：干运行模式的核心实现
   - 建议：如需修改，保留此方法但优化内部

2. **不建议修改 `always_include_csv` 的默认值**
   - 文件：`cv_agent/control/factory.py`
   - 原因：默认应该是最安全的（总是记录 CSV）
   - 建议：如需改变，必须经过维护者审批

3. **不建议在 `step()` 方法中添加 `apply_mouse` 的条件跳过**
   - 文件：`vision/stream/realtime_loop.py`
   - 原因：所有路径都必须记录 CSV
   - 建议：使用分支（if/else）确保总是调用 log_only() 或 apply_correction()

---

## Agent 允许操作清单

### ✅ 允许的改动类型

1. **内部性能优化**（不改变外部 API）
   - 示例：优化 `log_only()` 的计算方法
   - 条件：保持相同的输入/输出行为

2. **新后端扩展**（遵循 ChainedBackend 架构）
   - 示例：添加 `LinuxMouseBackend` 类
   - 条件：必须继承 `BaseMouseBackend` 并支持链式调用

3. **诊断/日志增强**（不影响控制流）
   - 示例：在 CSV 中添加新的元数据列
   - 条件：不能改变 flush() 机制

4. **测试覆盖扩展**
   - 示例：添加更多的单元测试
   - 条件：测试必须验证约束（不是绕过约束）

5. **文档更新**
   - 示例：更新 API 文档或示例代码
   - 条件：不能改变实际行为

---

## Codex 工作流检查清单

**在执行任何代码生成任务时，Agent 必须：**

- [ ] 阅读并理解 `.github/copilot-instructions.md` 的第 6 节检查清单
- [ ] 检查涉及 `cv_agent.control` 的改动是否被 Level 1 禁止操作覆盖
- [ ] 验证 CSV 日志路径不被修改或污染
- [ ] 确认 apply_mouse 参数能够正确传递
- [ ] 测试 ChainedBackend 的链式功能（如涉及）
- [ ] 检查 try...finally 块是否完整（涉及资源释放）
- [ ] 确认命令行参数的默认值是安全的（干运行）

---

## 版本与维护

- **版本**：1.0
- **最后更新**：2026-09-09
- **维护者**：AI Game Security Lab 团队
- **审批**：代码审查 + 自动 CI 检查

---

## 快速参考：常见违规模式

| 违规模式 | 位置 | 级别 | 建议 |
|---------|------|------|------|
| `apply_mouse=False` 硬编码 | realtime_loop.step() | 🔴 | 使用 if/else 分支判断 |
| 删除 ChainedBackend | control/backends/ | 🔴 | 绝不删除，只能扩展 |
| 跳过 CSV 记录 | 任何控制路径 | 🔴 | 两个分支都要调用后端 |
| 移除 flush() | CSVLoggerBackend | 🔴 | 每次 send_relative_move() 后必须 flush() |
| 强制 dry_run=True | Win32APIBackend | 🔴 | 允许 Hook 注入改变此值 |
| 移除 Kill Switch | safety.py | 🔴 | 这是安全机制，绝不移除 |
| --apply-mouse 参数删除 | CLI 参数 | 🔴 | 这是用户的唯一动态控制方式 |
| 修改默认值为 True | apply_mouse default | 🔴 | 默认必须是干运行（安全）|

---

## 相关文件关系图

```
.github/copilot-instructions.md (📖 详细规范，500+ 行)
    ↓
.copilot-instructions.md (📌 快速参考，项目根目录)
    ↓
AGENTS.md (⚙️ Agent 配置，本文件)
    ↓
.github/workflows/codex-compliance.yml (🔍 自动检查 CI)
    ↓
PR 审查流程
```

---

## 联系方式

- 📧 报告违规：GitHub Issues
- 💬 讨论规则：GitHub Discussions
- 🚨 紧急情况：直接联系维护者
