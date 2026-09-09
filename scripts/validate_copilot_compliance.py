#!/usr/bin/env python3
"""
Copilot Compliance Checker
验证代码是否违反 .github/copilot-instructions.md 中的规范
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


class ComplianceChecker:
    """检查代码是否遵守 Copilot 约束"""
    
    def __init__(self, repo_root: Path = None):
        self.repo_root = repo_root or Path.cwd()
        self.violations: List[Tuple[str, int, str, str]] = []  # (file, line, type, message)
        self.warnings: List[Tuple[str, int, str, str]] = []    # (file, line, type, message)
    
    def check_all(self) -> bool:
        """运行所有检查，返回是否通过"""
        self._check_chained_backend()
        self._check_apply_mouse_hardcoding()
        self._check_csv_logging()
        self._check_factory_always_include_csv()
        self._check_kill_switch()
        self._check_try_finally_blocks()
        
        # 输出结果
        self._print_results()
        
        # 如果有违规，返回失败
        return len(self.violations) == 0
    
    def _check_chained_backend(self) -> None:
        """检查 ChainedBackend 是否存在"""
        chained_path = self.repo_root / "cv_agent/control/backends/chained.py"
        if not chained_path.exists():
            self.violations.append((
                str(chained_path),
                0,
                "MISSING_CLASS",
                "ChainedBackend class is missing - critical architecture component"
            ))
        else:
            # 检查是否有 send_relative_move 方法
            try:
                content = chained_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                content = chained_path.read_text(encoding='gbk')
            if "def send_relative_move" not in content:
                self.violations.append((
                    str(chained_path),
                    0,
                    "BROKEN_API",
                    "ChainedBackend.send_relative_move() method is missing"
                ))
    
    def _check_apply_mouse_hardcoding(self) -> None:
        """检查 apply_mouse 是否被硬编码为 False"""
        files_to_check = [
            "vision/stream/realtime_loop.py",
            "cv_agent/orchestrator.py",
        ]
        
        for file_rel in files_to_check:
            file_path = self.repo_root / file_rel
            if not file_path.exists():
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                content = file_path.read_text(encoding='gbk')
            lines = content.split("\n")
            
            for i, line in enumerate(lines, 1):
                # 检查硬编码的 apply_mouse=False（排除注释和合理的默认值）
                if re.search(r'\bapply_mouse\s*=\s*False\b', line):
                    # 排除合理的情况
                    should_skip = False
                    
                    # 基本排除条件
                    if (
                        line.strip().startswith('#') or  # 注释行
                        'RealtimeLoopConfig' in line or  # 配置默认值
                        'default' in line.lower() or     # 默认值声明
                        'False  # ✔' in line             # 已标注的合法代码
                    ):
                        should_skip = True
                    
                    # 检查当前行和前后行的上下文（防止漏报）
                    if not should_skip:
                        context_start = max(0, i - 3)
                        context_end = min(len(lines), i + 2)
                        context_lines = lines[context_start:context_end]
                        context = " ".join(context_lines)
                        
                        # 检查是否有合法的上下文标记
                        if (
                            ('✔' in context and '干运行' in context) or      # 中文标记
                            ('✔' in context and 'dry-run' in context) or     # 英文标记
                            '# ✔ MUST' in context or                         # MUST 规范
                            'pipeline.run' in context or                     # pipeline 调用
                            'ALWAYS' in context or                           # ALWAYS 标记
                            '无条件' in context                               # 无条件标记
                        ):
                            should_skip = True
                    
                    if should_skip:
                        continue
                    
                    self.violations.append((
                        str(file_path),
                        i,
                        "HARDCODED_APPLY_MOUSE",
                        f"apply_mouse hardcoded to False: {line.strip()}"
                    ))
    
    def _check_csv_logging(self) -> None:
        """检查 CSV 日志是否被正确实现"""
        csv_logger_path = self.repo_root / "cv_agent/control/backends/csv_logger.py"
        if not csv_logger_path.exists():
            self.violations.append((
                str(csv_logger_path),
                0,
                "MISSING_CSV",
                "CSVLoggerBackend is missing"
            ))
        else:
            try:
                content = csv_logger_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                content = csv_logger_path.read_text(encoding='gbk')
            
            # 检查 send_relative_move 是否调用 flush()
            if "def send_relative_move" in content:
                # 找到 send_relative_move 方法
                match = re.search(
                    r'def send_relative_move\(.*?\):\s*(?:.*?\n)*?(?=\n    def |\Z)',
                    content,
                    re.DOTALL
                )
                if match:
                    method_content = match.group()
                    if "flush()" not in method_content:
                        self.warnings.append((
                            str(csv_logger_path),
                            0,
                            "MISSING_FLUSH",
                            "send_relative_move() should call flush() after writerow()"
                        ))
    
    def _check_factory_always_include_csv(self) -> None:
        """检查工厂函数是否支持 always_include_csv"""
        factory_path = self.repo_root / "cv_agent/control/factory.py"
        if not factory_path.exists():
            return
        
        try:
            content = factory_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = factory_path.read_text(encoding='gbk')
        
        # 检查参数是否存在
        if "always_include_csv" not in content:
            self.warnings.append((
                str(factory_path),
                0,
                "MISSING_PARAM",
                "create_mouse_backend() should have always_include_csv parameter"
            ))
        
        # 检查 ChainedBackend 是否被使用
        if "ChainedBackend" not in content:
            self.warnings.append((
                str(factory_path),
                0,
                "MISSING_CHAIN",
                "create_mouse_backend() should use ChainedBackend for multi-backend support"
            ))
    
    def _check_kill_switch(self) -> None:
        """检查全局热键 Kill Switch 是否存在"""
        safety_path = self.repo_root / "vision/stream/safety.py"
        if not safety_path.exists():
            self.violations.append((
                str(safety_path),
                0,
                "MISSING_SAFETY",
                "GlobalHotkeyKillSwitch is missing"
            ))
        else:
            try:
                content = safety_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                content = safety_path.read_text(encoding='gbk')
            if "VK_ESCAPE" not in content or "VK_F12" not in content:
                self.violations.append((
                    str(safety_path),
                    0,
                    "BROKEN_HOTKEYS",
                    "Emergency hotkeys (ESC/F12) are missing or misconfigured"
                ))
    
    def _check_try_finally_blocks(self) -> None:
        """检查关键位置是否有 try...finally 块"""
        realtime_path = self.repo_root / "vision/stream/realtime_loop.py"
        if not realtime_path.exists():
            return
        
        try:
            content = realtime_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = realtime_path.read_text(encoding='gbk')
        
        # 检查 run() 方法是否有 finally 块
        run_method_match = re.search(
            r'def run\(.*?\):\s*(?:.*?\n)*?(?=\n    def |\Z)',
            content,
            re.DOTALL
        )
        
        if run_method_match:
            run_method = run_method_match.group()
            if "finally:" not in run_method:
                self.violations.append((
                    str(realtime_path),
                    0,
                    "MISSING_FINALLY",
                    "run() method should have finally block for resource cleanup"
                ))
            
            if "controller.close()" not in run_method:
                self.violations.append((
                    str(realtime_path),
                    0,
                    "MISSING_CLOSE",
                    "finally block should call pipeline.controller.close()"
                ))
    
    def _print_results(self) -> None:
        """输出检查结果"""
        print("\n" + "=" * 70)
        print("COPILOT COMPLIANCE CHECK RESULTS")
        print("=" * 70)
        
        if self.violations:
            print(f"\n🔴 VIOLATIONS FOUND: {len(self.violations)}")
            for file, line, violation_type, msg in self.violations:
                print(f"  • {file}:{line}")
                print(f"    [{violation_type}] {msg}")
        else:
            print(f"\n✅ NO VIOLATIONS FOUND")
        
        if self.warnings:
            print(f"\n🟡 WARNINGS: {len(self.warnings)}")
            for file, line, warning_type, msg in self.warnings:
                print(f"  • {file}:{line}")
                print(f"    [{warning_type}] {msg}")
        else:
            print(f"✅ NO WARNINGS")
        
        print("\n" + "=" * 70)
        if self.violations:
            print("❌ COMPLIANCE CHECK FAILED - Fix violations before committing")
            print("=" * 70)
        else:
            print("✅ COMPLIANCE CHECK PASSED")
            print("=" * 70)


if __name__ == "__main__":
    repo_root = Path.cwd()
    if not (repo_root / ".github" / "copilot-instructions.md").exists():
        # Try parent directory
        if (repo_root.parent / ".github" / "copilot-instructions.md").exists():
            repo_root = repo_root.parent
        else:
            print("Error: Could not find .github/copilot-instructions.md")
            sys.exit(1)
    
    checker = ComplianceChecker(repo_root)
    success = checker.check_all()
    
    sys.exit(0 if success else 1)
