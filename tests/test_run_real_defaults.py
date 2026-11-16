from pathlib import Path

import run_real


def test_run_real_adds_pre_finetune_default_by_default() -> None:
    argv = run_real._ensure_default_args(["run_real.py", "--backend", "win32"])

    assert "--weights" in argv
    weights = Path(argv[argv.index("--weights") + 1])
    assert weights == run_real._DEFAULT_WEIGHTS
    assert weights.name == "best.onnx"
    assert "cs2_detection_v2" in str(weights)


def test_run_real_preserves_explicit_finetuned_weights() -> None:
    argv = run_real._ensure_default_args(
        ["run_real.py", "--weights", r"runs\detect\cs2_multitarget_ft_v1\weights\best.onnx"]
    )

    assert argv.count("--weights") == 1
    assert argv[argv.index("--weights") + 1].endswith("cs2_multitarget_ft_v1\\weights\\best.onnx")


def test_run_real_preserves_equals_form_weights() -> None:
    argv = run_real._ensure_default_args(
        ["run_real.py", "--weights=runs\\detect\\cs2_detection_v2\\weights\\best.onnx"]
    )

    assert not any(arg == "--weights" for arg in argv)
    assert any(arg.startswith("--weights=") for arg in argv)