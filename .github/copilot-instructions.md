# Codex / GitHub Copilot 代码生成与安全约束规范

## 📋 文档版本
- **版本**：1.0
- **最后更新**：2026-09-09
- **生效范围**：所有代码生成、重构、PR 审查任务
- **优先级**：🔴 **CRITICAL** - 违反本规范的改动将被拒绝合并

---

## 1. 控制层与后端策略 (cv_agent.control)

### 1.1 apply_mouse 参数严格约束

#### ❌ **禁止行为**
```python
# 错误示例 - 将被视为安全漏洞
def step(self, frame: np.ndarray | None = None):
    result = self.pipeline.run(frame, apply_mouse=False)  # ❌ 硬编码为 False
    if result.selected:
        # ❌ 不调用 log_only() 或 apply_correction()
        pass
```

#### ✅ **强制行为**
```python
# 正确示例 - 必须遵循此模式
def step(self, frame: np.ndarray | None = None):
    result = self.pipeline.run(frame, apply_mouse=False)  # ✔ 总是 False（不发送 mouse 事件）
    if result.selected is None or result.compensated_offset is None:
        self.pipeline.controller.reset()
    else:
        # ✔ MUST: 检查 self.config.apply_mouse 标志
        if self.config.apply_mouse and not self._mouse_paused():
            # ✔ MUST: 调用 apply_correction()（CSV + 真实控制）
            self.pipeline.controller.apply_correction(
                *result.compensated_offset,
                max_step=self.config.max_mouse_step,
                deadzone=self.config.mouse_deadzone,
            )
            result = replace(result, applied_mouse=True)
        else:
            # ✔ MUST: 调用 log_only()（仅 CSV 记录，干运行）
            self.pipeline.controller.log_only(
                *result.compensated_offset,
                max_step=self.config.max_mouse_step,
                deadzone=self.config.mouse_deadzone,
            )
            # ✔ MUST: applied_mouse 保持 False
    return result
```

### 1.2 RealtimeLoopConfig 配置

```python
# ✔ MUST: apply_mouse 必须是可配置参数
@dataclass(frozen=True, slots=True)
class RealtimeLoopConfig:
    algorithm: str | None = None
    apply_mouse: bool = False  # ✔ 默认 False（干运行）
    delay_s: float | None = None
    # ...其他配置...
```

### 1.3 命令行参数式

```bash
# ✔ MUST: 支持 --apply-mouse 参数显式启用真实控制
python vision/stream/realtime_loop.py --apply-mouse --backend win32

# ✔ MUST: 默认不启用（干运行模式）
python vision/stream/realtime_loop.py
# 等同于：python vision/stream/realtime_loop.py --backend csv
```

---

## 2. ChainedBackend & 多后端链式架构

### 2.1 多后端链式要求

#### ✔ **强制实现**
- `cv_agent/control/backends/chained.py` 中必须存在 `ChainedBackend` 类
- `ChainedBackend` 在 `send_relative_move()` 时必须依次分发到所有链中的后端
- 禁止删除或重命名此类

#### ❌ **禁止行为**
```python
# ❌ 不允许删除 ChainedBackend
# ❌ 不允许将 ChainedBackend 标记为 @deprecated
# ❌ 不允许改变其 API 签名（特别是 __init__ 和 send_relative_move）
```

#### ✅ **正确行为**
```python
# ✔ MUST: ChainedBackend 支持多后端
class ChainedBackend(BaseMouseBackend):
    def __init__(self, backends: Sequence[BaseMouseBackend], *, strict: bool = False):
        """Chain multiple backends together."""
    
    def send_relative_move(self, dx: int, dy: int) -> None:
        """Send to ALL backends in sequence."""
        for backend in self._backends:
            try:
                backend.send_relative_move(int(dx), int(dy))
            except Exception as e:
                if self._strict:
                    raise
```

### 2.2 Factory 函数式（always_include_csv）

#### ✔ **MUST**
```python
def create_mouse_backend(
    name: str = "csv",
    *,
    output_path: str | Path | None = None,
    allow_external_handler: bool = False,
    custom_handler: Callable[[int, int], None] | None = None,
    always_include_csv: bool = True,  # ✔ MUST: 此参数必须存在
) -> BaseMouseBackend:
    """
    ✔ MUST: 当 always_include_csv=True 且 name != "csv" 时，
            返回 ChainedBackend([CSVLoggerBackend, primary_backend])
    """
    if key == "csv":
        return CSVLoggerBackend(output_path)
    
    primary_backend = _create_primary_backend(name, ...)
    
    # ✔ MUST: 检查链式条件
    if always_include_csv and key != "csv":
        csv_backend = CSVLoggerBackend(output_path)
        return ChainedBackend([csv_backend, primary_backend])
    
    return primary_backend
```

---

## 3. 数据落盘与日志保证

### 3.1 CSV 记录强制性

#### ❌ **禁止行为**
```python
# ❌ 不允许存在只调用真实控制而不记录的代码路径
if self.config.apply_mouse:
    self.backend.send_relative_move(dx, dy)  # ❌ 如果 backend 不是 ChainedBackend
# ❌ 结果：可能跳过 CSV 记录

# ❌ 不允许条件判断跳过 CSV
if some_condition:
    # ❌ CSV 日志初始化被跳过
    self.csv_logger = None
```

#### ✔ **强制行为**
```python
# ✔ MUST: 所有控制移动都记录到 CSV（无条件）
def log_only(self, dx: float, dy: float, ...):
    """MUST: 计算并记录偏移到 CSV（干运行）"""
    # ... 计算逻辑 ...
    self.backend.send_relative_move(sx, sy)  # ✔ 调用后端（CSV 会记录）

def apply_correction(self, dx: float, dy: float, ...):
    """MUST: 计算、记录到 CSV 并发送真实控制"""
    # ... 计算逻辑 ...
    self.backend.send_relative_move(sx, sy)  # ✔ ChainedBackend 会分发给 CSV + Win32
```

### 3.2 Flush 机制

#### ✔ **MUST**
```python
class CSVLoggerBackend(BaseMouseBackend):
    def send_relative_move(self, dx: int, dy: int) -> None:
        self._writer.writerow([...])  # 写入记录
        self._handle.flush()          # ✔ MUST: 立即刷新，防止数据丢失

    def close(self) -> None:
        # ✔ MUST: 显式关闭时也刷新
        try:
            self._handle.flush()
        finally:
            self._handle.close()
```

### 3.3 文件输出目录与命名

#### ✔ **MUST**
```python
# ✔ MUST: 默认输出到 runs/predict/ 目录
DEFAULT_PATH = Path("runs/predict") / f"control_moves_{time.strftime('%Y%m%d_%H%M%S')}.csv"

# ✔ MUST: 允许通过 --backend-output 参数自定义路径
# 使用方式：python vision/stream/realtime_loop.py --backend-output /custom/path.csv
```

---

## 4. 紧急安全机制

### 4.1 Kill Switch 全局热键

#### ✔ **MUST**
```python
class GlobalHotkeyKillSwitch:
    """
    ✔ MUST: 保留此类及以下功能：
    - ESC 键：暂停鼠标输出（paused=True）
    - F12 键：停止运行（stopped=True）
    
    ✔ MUST: 这两个热键不能被 apply_mouse 或任何其他参数禁用
    """
    
    def __init__(self, bindings: HotkeyBindings | None = None):
        self.paused = False
        self.stopped = False
        self.bindings = bindings or HotkeyBindings(
            pause_vk=VK_ESCAPE,  # ✔ ESC
            stop_vk=VK_F12,      # ✔ F12
        )
```

### 4.2 暂停检查逻辑

#### ✔ **MUST**
```python
def step(self, frame):
    # ✔ MUST: 在执行任何控制前检查暂停状态
    if self._mouse_paused():  # 检查 kill_switch.paused
        # ... 不发送控制 ...
        return result
    
    # ✔ MUST: 在执行前检查停止状态
    if self._loop_stopped():  # 检查 kill_switch.stopped
        # 退出循环
        break
```

### 4.3 try...finally 资源释放

#### ✔ **MUST**
```python
def run(self, max_frames: int | None = None, *, preview: bool = False):
    try:
        # ... 主循环 ...
        while frame_idx < max_frames:
            if self._loop_stopped():
                break
            # ... 处理帧 ...
    finally:
        # ✔ MUST: 必须有 finally 块
        try:
            self.pipeline.controller.close()  # ✔ 关闭所有后端
        except Exception as e:
            print(f"[WARNING] Error: {e}")
        
        if preview or self.config.debug_overlay:
            try:
                cv2.destroyWindow(window_name)
            except Exception as e:
                print(f"[WARNING] Error: {e}")
```

---

## 5. run_real.py 动态注入机制

### 5.1 Hook 架构保护

#### ✔ **MUST**
```python
# ✔ MUST: run_real.py 是合法的真实驱动注入入口
# ✔ MUST: 通过 factory.create_mouse_backend 的 Hook 机制注入 custom_handler

def patched_create_mouse_backend(name: str, **kwargs):
    """✔ MUST: Hook 必须保留此功能"""
    if name == "win32":
        csv_backend = CSVLoggerBackend(...)
        win32_backend = Win32APIBackend(
            dry_run=False,  # ✔ dry_run=False（真实驱动）
            custom_handler=my_real_win32_handler  # ✔ 注入真实 handler
        )
        return ChainedBackend([csv_backend, win32_backend])
    # ...
```

#### ❌ **禁止行为**
```python
# ❌ 不允许删除或注释掉 Hook 机制
# ❌ 不允许改变 Hook 的签名
# ❌ 不允许强制 dry_run=True（必须由 Hook 决定）
```

---

## 6. 代码审查检查清单

Copilot 生成的任何涉及控制层的改动必须满足以下检查项：

### 6.1 参数与配置检查
- [ ] `apply_mouse` 不能被硬编码为 `False`
- [ ] `RealtimeLoopConfig.apply_mouse` 存在且可配置
- [ ] `--apply-mouse` 命令行参数存在
- [ ] 默认值为 `False`（干运行）

### 6.2 后端与链式检查
- [ ] `ChainedBackend` 类存在，API 未改变
- [ ] `create_mouse_backend()` 有 `always_include_csv` 参数
- [ ] Win32 后端能够通过 `custom_handler` 注入
- [ ] `allow_external_handler=True` 时允许外部 Handler

### 6.3 数据落盘检查
- [ ] 所有后端的 `send_relative_move()` 都调用 `flush()`
- [ ] CSV 文件在 `runs/predict/` 目录生成
- [ ] 文件名包含时间戳
- [ ] `close()` 方法显式刷新与关闭

### 6.4 安全机制检查
- [ ] `GlobalHotkeyKillSwitch` 存在
- [ ] ESC + F12 热键保留
- [ ] `_mouse_paused()` 检查在控制前
- [ ] `_loop_stopped()` 检查在主循环
- [ ] try...finally 块确保资源释放

### 6.5 Hook 机制检查
- [ ] `run_real.py` 能够通过 patching factory 注入 Hook
- [ ] Hook 创建 `ChainedBackend([CSV, Win32Real])`
- [ ] `dry_run=False` 用于真实驱动
- [ ] `custom_handler` 被正确传递

---

## 7. 违规示例与说明

### 错误改动示例 1：硬编码 apply_mouse=False

```python
# ❌ 违规：将被拒绝
def step(self, frame):
    result = self.pipeline.run(frame, apply_mouse=False)
    if result.selected:
        # ❌ 永远不调用任何记录或控制
        pass
    return result
```

**问题**：打破了动态控制的核心机制，用户无法启用真实控制。

### 错误改动示例 2：删除 ChainedBackend

```python
# ❌ 违规：不允许删除此类
# 原文件：cv_agent/control/backends/chained.py
# 改动：delete（或移动）
```

**问题**：失去了多后端同时工作的能力，无法同时记录 + 控制。

### 错误改动示例 3：跳过 CSV 日志

```python
# ❌ 违规：条件性跳过 CSV
def step(self, frame):
    result = self.pipeline.run(frame, apply_mouse=False)
    if result.selected and self.config.apply_mouse:
        # ❌ 只有在 apply_mouse=True 时才记录？
        self.pipeline.controller.log_only(...)
```

**问题**：干运行模式下无法获得轨迹日志，数据丢失。

### 错误改动示例 4：移除热键检查

```python
# ❌ 违规：移除 kill switch 检查
def step(self, frame):
    # ❌ 直接执行，不检查 _mouse_paused()
    self.pipeline.controller.apply_correction(
        *result.compensated_offset,
        ...
    )
```

**问题**：用户无法通过 ESC 暂停鼠标输出，存在安全隐患。

---

## 8. 合规改动示例

### ✅ 合规改动 1：添加新的后端类型

```python
# ✔ 允许：扩展后端类型
class CustomBackend(BaseMouseBackend):
    def send_relative_move(self, dx, dy):
        # ... 自定义逻辑...
        pass

# 在 factory 中注册
def create_mouse_backend(...):
    if name == "custom":
        custom_backend = CustomBackend()
        if always_include_csv:
            csv_backend = CSVLoggerBackend(...)
            return ChainedBackend([csv_backend, custom_backend])
        return custom_backend
```

**理由**：扩展功能，但不破坏现有约束。

### ✅ 合规改动 2：优化 log_only() 性能

```python
# ✔ 允许：内部优化
def log_only(self, dx, dy, ...):
    """优化：使用更高效的计算方法"""
    distance = math.hypot(float(dx), float(dy))
    if distance > deadzone:
        # 优化的计算逻辑（结果相同）
        sx, sy = _optimized_calculate(dx, dy)
    self.backend.send_relative_move(sx, sy)
```

**理由**：改进内部实现，保持行为不变。

### ✅ 合规改动 3：增强安全日志

```python
# ✔ 允许：增强日志信息
class CSVLoggerBackend:
    def send_relative_move(self, dx, dy):
        self._writer.writerow([
            time.time_ns(),
            int(dx),
            int(dy),
            repr(self._context),
            f"apply_mouse={self._apply_mouse}",  # ✔ 新增字段
        ])
        self._handle.flush()
```

**理由**：增加调试信息，不改变核心行为。

---

## 9. 违规处置流程

1. **自动检测**：PR 时触发 CI 检查（参见 `.github/workflows/codex-compliance.yml`）
2. **警告报告**：违规信息详细输出到 PR 评论
3. **拒绝合并**：包含违规改动的 PR 不允许合并
4. **人工审查**：根据严重程度决定是否需要人工介入

---

## 10. 紧急更新流程

若需要更新此文档，请：

1. 创建新的 Issue 或 Discussion
2. 标记为 `[SECURITY]` 或 `[COPILOT-RULES]`
3. 详细说明改动原因
4. 至少两名审查者同意
5. 更新文档版本号

---

## 附录 A：快速检查脚本

```bash
#!/bin/bash
# scripts/validate-copilot-compliance.sh
# 用于本地快速检查是否违反 Copilot 约束

echo "Checking Copilot compliance..."

# 检查 apply_mouse 是否被硬编码
if grep -r "apply_mouse.*=.*False" cv_agent/control/ vision/stream/ --include="*.py" | grep -v "# ✔" | grep -v "RealtimeLoopConfig"; then
    echo "❌ FAIL: apply_mouse hardcoded to False"
    exit 1
fi

# 检查 ChainedBackend 是否存在
if [ ! -f "cv_agent/control/backends/chained.py" ]; then
    echo "❌ FAIL: ChainedBackend not found"
    exit 1
fi

# 检查 CSV 初始化是否被跳过
if grep -r "csv_backend.*=.*None" cv_agent/control/ --include="*.py"; then
    echo "❌ FAIL: CSV backend initialization skipped"
    exit 1
fi

echo "✅ PASS: All compliance checks passed"
exit 0
```

---

## 联系方式

- **问题报告**：提交 Issue 标记为 `[COPILOT-COMPLIANCE]`
- **规则更新**：讨论区发起 Discussion
- **紧急修复**：立即通知维护者
