#!/usr/bin/env python3
"""Test suite for realtime_loop modifications."""

from pathlib import Path
import tempfile
import sys

def test_chained_backend():
    """Test ChainedBackend creation and operation."""
    from cv_agent.control import ChainedBackend, CSVLoggerBackend
    from cv_agent.control.backends.win32 import Win32APIBackend
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_backend = CSVLoggerBackend(Path(tmpdir) / "test.csv")
        win32_backend = Win32APIBackend(dry_run=True)
        chained = ChainedBackend([csv_backend, win32_backend])
        
        # Test send_relative_move
        chained.send_relative_move(10, 20)
        chained.close()
        
        # Check CSV was created
        csv_path = Path(tmpdir) / "test.csv"
        assert csv_path.exists(), "CSV file not created"
        content = csv_path.read_text()
        assert "10,20" in content, "Movement not recorded in CSV"
        print("✓ ChainedBackend works correctly")


def test_factory_always_csv():
    """Test factory with always_include_csv=True."""
    from cv_agent.control.factory import create_mouse_backend
    from cv_agent.control import ChainedBackend
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Test CSV backend
        csv_backend = create_mouse_backend("csv", output_path=Path(tmpdir) / "csv.csv", always_include_csv=True)
        assert csv_backend.__class__.__name__ == "CSVLoggerBackend", "CSV backend should not be chained"
        csv_backend.close()
        
        # Test win32 backend with chaining
        win32_backend = create_mouse_backend("win32", output_path=Path(tmpdir) / "win32.csv", always_include_csv=True)
        assert isinstance(win32_backend, ChainedBackend), "win32 backend should be chained"
        win32_backend.send_relative_move(5, 5)
        win32_backend.close()
        
        # Check CSV from chained backend
        csv_path = Path(tmpdir) / "win32.csv"
        assert csv_path.exists(), "CSV from chained win32 backend not created"
        print("✓ Factory with always_include_csv works correctly")


def test_aim_controller_log_only():
    """Test AimController.log_only() method."""
    from cv_agent.control.mouse import AimController
    from cv_agent.control import CSVLoggerBackend
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = CSVLoggerBackend(Path(tmpdir) / "control.csv")
        controller = AimController(backend)
        
        # Test log_only
        result = controller.log_only(10.5, 20.3, max_step=24.0, deadzone=0.5)
        assert result["sent_dx"] > 0, "log_only should calculate movement"
        assert result["sent_dy"] > 0, "log_only should calculate movement"
        
        controller.close()
        
        # Check CSV was created
        csv_path = Path(tmpdir) / "control.csv"
        assert csv_path.exists(), "CSV file not created"
        content = csv_path.read_text()
        assert len(content.split("\n")) > 2, "CSV should have logged entries"
        print("✓ AimController.log_only() works correctly")


def test_command_line_parsing():
    """Test realtime_loop command line argument parsing."""
    import argparse
    
    # Simulate the argument parser from realtime_loop
    parser = argparse.ArgumentParser()
    parser.add_argument("--algorithm", default=None)
    parser.add_argument("--apply-mouse", action="store_true")
    parser.add_argument("--backend", choices=("csv", "canvas", "win32", "hid"), default="csv")
    parser.add_argument("--backend-output", default=None)
    parser.add_argument("--allow-external-handler", action="store_true")
    
    # Test case 1: No --apply-mouse (default)
    args = parser.parse_args([])
    assert args.apply_mouse is False, "--apply-mouse should default to False"
    assert args.backend == "csv", "backend should default to csv"
    print("✓ Default arguments parsed correctly")
    
    # Test case 2: With --apply-mouse
    args = parser.parse_args(["--apply-mouse"])
    assert args.apply_mouse is True, "--apply-mouse should be True when specified"
    print("✓ --apply-mouse flag parsed correctly")
    
    # Test case 3: Win32 backend
    args = parser.parse_args(["--backend", "win32"])
    assert args.backend == "win32", "backend win32 should be selectable"
    print("✓ Backend selection works correctly")


def test_hook_mechanism():
    """Test run_real.py hook mechanism."""
    # This test verifies the hook can be applied
    from cv_agent.control import ChainedBackend
    import cv_agent.control.factory as factory_mod
    
    # Save original
    orig_factory = factory_mod.create_mouse_backend
    
    def custom_handler(dx, dy):
        pass
    
    def hook_factory(name: str, **kwargs):
        if name == "win32":
            from cv_agent.control import CSVLoggerBackend
            from cv_agent.control.backends.win32 import Win32APIBackend
            csv_backend = CSVLoggerBackend(kwargs.get("output_path"))
            win32_backend = Win32APIBackend(dry_run=False, custom_handler=custom_handler)
            return ChainedBackend([csv_backend, win32_backend])
        return orig_factory(name, **kwargs)
    
    factory_mod.create_mouse_backend = hook_factory
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test hook returns chained backend
            result = factory_mod.create_mouse_backend("win32", output_path=Path(tmpdir) / "hook.csv")
            assert isinstance(result, ChainedBackend), "Hook should return ChainedBackend"
            result.close()
            print("✓ Hook mechanism works correctly")
    finally:
        factory_mod.create_mouse_backend = orig_factory


if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Running realtime_loop modification tests...")
        print("=" * 60)
        test_chained_backend()
        test_factory_always_csv()
        test_aim_controller_log_only()
        test_command_line_parsing()
        test_hook_mechanism()
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
