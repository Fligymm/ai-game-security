【修改总结】Vision 模块实时循环架构安全加固与控制动态启用

## 核心修改内容

### 1️⃣ ChainedBackend（多后端链式支持）
**文件**：`cv_agent/control/backends/chained.py`（新建）

- 创建 `ChainedBackend` 类，支持将多个后端链接在一起
- 每个 `send_relative_move()` 调用会依次分发到所有链中的后端
- 用于**同时进行 CSV 记录和真实控制**
- 完整的资源释放：`close()` 按逆序闭包所有后端

```python
# 用法示例
csv_backend = CSVLoggerBackend(...)
win32_backend = Win32APIBackend(dry_run=False, custom_handler=handler)
chained = ChainedBackend([csv_backend, win32_backend])
```

### 2️⃣ 工厂函数增强
**文件**：`cv_agent/control/factory.py`

- 新增 `always_include_csv` 参数（默认 `True`）
- 当选择非 CSV 后端时，自动链接 CSV 记录
- 确保**无论如何都会保留轨迹日志**

```python
# CSV 后端单独使用（防止双链）
backend = create_mouse_backend("csv", always_include_csv=True)  
# → CSVLoggerBackend

# Win32 + CSV 自动链接
backend = create_mouse_backend("win32", always_include_csv=True)  
# → ChainedBackend([CSVLoggerBackend, Win32APIBackend])
```

### 3️⃣ AimController 控制逻辑分离
**文件**：`cv_agent/control/mouse.py`

新增 `log_only()` 方法，与 `apply_correction()` 配合使用：

| 方法 | 场景 | 行为 |
|------|------|------|
| `log_only()` | apply_mouse=False | 计算偏移 → CSV 记录（干运行） |
| `apply_correction()` | apply_mouse=True | 计算偏移 → CSV + 后端执行 |

两个方法都会处理分数舍入，保证位移精确。

### 4️⃣ RealtimeAimLoop 步进逻辑重构
**文件**：`vision/stream/realtime_loop.py`

#### 新 step() 方法流程
```
frame → pipeline.run() → check offset
  ├─ if apply_mouse=True & not paused:
  │   └─ controller.apply_correction()  [CSV + 真实控制]
  │       └─ 设置 applied_mouse=True
  └─ else:
      └─ controller.log_only()  [仅 CSV 记录]
          └─ 保持 applied_mouse=False
```

#### 关键特性
- **无条件日志**：即使干运行也记录 CSV
- **条件控制**：仅当 `--apply-mouse` 且 `--backend win32/hid` 时发送真实控制
- **紧急停止**：保留 ESC/F12 kill switch（并且不受 apply_mouse 影响）

### 5️⃣ 命令行参数调整
**文件**：`vision/stream/realtime_loop.py`（main 部分）

```bash
# 原参数（已移除）
--no-mouse          # 禁用鼠标（现已废弃）

# 新参数
--apply-mouse       # 显式启用真实鼠标控制（可选，默认干运行）
--backend csv|win32|canvas|hid
--backend-output    # CSV 输出路径（默认 runs/predict/control_moves_YYYYMMDD_HHMMSS.csv）
--allow-external-handler  # 允许外部 Handler 注入
```

#### 使用场景

| 命令 | 行为 |
|------|------|
| `python vision/stream/realtime_loop.py` | CSV 仅记录，无鼠标移动（默认干运行） |
| `python vision/stream/realtime_loop.py --apply-mouse --backend win32` | CSV + 真实鼠标控制（需真实 handler） |
| `python run_real.py` | Hook 注入真实 handler，自动启用链式后端 + CSV + 控制 |

### 6️⃣ run_real.py 增强
**文件**：`run_real.py`

- 改进 Hook 机制，创建链式后端：`ChainedBackend([CSVLoggerBackend, Win32APIBackend(real_handler)])`
- 自动设置 `--backend win32 --apply-mouse`
- 打印明确的启动信息

```python
# Hook 逻辑
def patched_create_mouse_backend(name: str, **kwargs):
    if name == "win32":
        csv_backend = CSVLoggerBackend(...)
        win32_backend = Win32APIBackend(dry_run=False, custom_handler=real_handler)
        return ChainedBackend([csv_backend, win32_backend])
    ...
```

### 7️⃣ 资源释放保障
**文件**：`vision/stream/realtime_loop.py`

#### run() 方法的 finally 块
```python
finally:
    try:
        self.pipeline.controller.close()  # 显式关闭后端 → 刷新 CSV、释放资源
    except Exception as e:
        print(f"[WARNING] Error closing controller: {e}")
    
    try:
        cv2.destroyWindow(window_name)
    except Exception as e:
        print(f"[WARNING] Error destroying window: {e}")
```

#### 主脚本的 finally 块
```python
finally:
    try:
        pipeline.controller.close()  # 保险级别关闭
    except Exception as e:
        print(f"[WARNING] Error: {e}")
```

---

## 数据安全承诺

### ✅ CSV 日志保证
1. **始终创建**：无论 `apply_mouse` 是否启用，都会在 `runs/predict/` 创建时间戳文件
2. **实时刷新**：每次 `send_relative_move()` 后立即 `flush()`，防止数据丢失
3. **完整记录**：时间戳 (ns) + dx + dy + 上下文元数据

### ✅ 控制安全
1. **干运行默认**：未指定 `--apply-mouse` 时，控制指令计算但不发送
2. **显式启用**：需要 `--apply-mouse --backend win32` 才能发送真实鼠标
3. **紧急停止**：ESC/F12 会停止所有控制并保让日志完成

### ✅ 资源释放
1. `try...finally` 覆盖所有退出路径
2. `backend.close()` 显式调用，确保 CSV 文件刷新完毕
3. 异常被捕获并日志记录，不会导致进程卡死

---

## 使用示例

### 场景 1：数据收集（干运行）
```bash
python vision/stream/realtime_loop.py --backend csv
# 输出：runs/predict/control_moves_20260909_143025.csv
# 效果：记录预测的鼠标轨迹，不发送任何控制信号
```

### 场景 2：测试真实控制
```bash
python run_real.py
# Hook 自动注入：
# - backend: win32 
# - apply_mouse: 启用
# - handler: 真实 Win32 鼠标驱动
# 输出：CSV 日志 + 真实鼠标移动
```

### 场景 3：仅可视化
```bash
python vision/stream/realtime_loop.py --backend canvas --preview
# 不发送任何控制，只显示预测结果
```

### 场景 4：自定义后端
```bash
python vision/stream/realtime_loop.py --backend win32 --allow-external-handler
# 允许外部代码注入自定义 handler
```

---

## 测试验证

实行了两套测试套件：

### ① 单元测试 (`test_realtime_modifications.py`)
✅ ChainedBackend 创建与操作  
✅ Factory 链式后端  
✅ AimController.log_only()  
✅ 命令行参数解析  
✅ Hook 机制  

### ② 集成测试 (`test_integration_realtime.py`)
✅ 干运行模式配置  
✅ 活动控制模式配置  
✅ CSV 后端选择  
✅ 控制器日志逻辑  
✅ run_real.py Hook 集成  

所有测试都通过 ✓

---

## 架构图

```
┌──────────────────────────────────────────────────────────┐
│  RealtimeAimLoop.step()                                  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  pipeline.run() → offset (dx, dy)                       │
│         ↓                                                │
│  apply_mouse=True?                                      │
│    ├─ YES: controller.apply_correction()               │
│    │         ↓                                          │
│    │    ChainedBackend([CSV, Win32])                   │
│    │         ├─ CSV: write timestamp+dx+dy            │
│    │         └─ Win32: send real input                │
│    │         ↓                                          │
│    │    applied_mouse = True                           │
│    │                                                    │
│    └─ NO: controller.log_only()                        │
│             ↓                                          │
│        ChainedBackend or CSVLoggerBackend              │
│             ├─ CSV: write timestamp+dx+dy            │
│             └─ (No real control)                      │
│             ↓                                          │
│        applied_mouse = False                          │
│                                                       │
└──────────────────────────────────────────────────────────┘
                        ↓
                  finally block
                        ↓
            controller.close()
            ├─ ChainedBackend.close()
            │   ├─ CSVLoggerBackend.close(): flush + close file
            │   └─ Win32APIBackend.close(): (noop)
            └─ [Resource cleanup complete]
```

---

## 向后兼容性

- ✅ 原有 CSV 后端工作流保持不变
- ✅ `--no-mouse` 已移除，用 `--apply-mouse` 反转之
- ✅ run_real.py 完全兼容（Hook 已更新）
- ✅ 新旧代码可共存工作

---

## 总结

此修改通过以下方式实现了用户需求：

1. ✅ **解除硬编码锁定**：`apply_mouse` 通过 CLI `--apply-mouse` 动态控制
2. ✅ **真实控制启用**：支持 win32/hid + custom_handler 注入
3. ✅ **无条件日志**：任何模式都会保留 CSV 轨迹
4. ✅ **安全防护**：try...finally 确保资源与日志完整释放
5. ✅ **紧急停止**：F12/ESC 保持可用且不阻塞日志

系统已全面测试，可投入使用。🚀
