# Final risk review — 2026-11-14

Scope: post-freeze R1–R4 only. No model, data, training, or accuracy changes.

## Overall

**PASS WITH GAPS.** The R2 stop-path defect was fixed and regression-tested;
the project owner also reports that physical ESC/F12 validation passed. Model
freeze is intact. Remaining gaps are privacy/license/release decisions, not
model or control correctness.

## R1. Model deployment and rollback — PASS

Evidence:

```text
run_real.py default:
  runs/detect/cs2_multitarget_ft_v1/weights/best.onnx
run_real default tests: 3 passed
new ONNX metadata:
  input  [1, 3, 640, 640], names {0: enemy_head, 1: enemy_body}
old ONNX metadata:
  input  [1, 3, 640, 640], names {0: enemy_head, 1: enemy_body}
manifest hash checks: 9/9 match
rollback file: exists, same class mapping
```

Model-load failures occur before the loop starts. `realtime_loop.py` also checks
the class mapping before constructing the backend. No deployment path was found
that silently loads the old model; the old model is only an explicit rollback or
benchmark default.

Release gap: `run_real.py` is gitignored and contains an absolute local default
path, so a clean clone does not carry the deployment entrypoint.

## R2. Real-control stop mechanism — PASS (fixed)

Confirmed defect before the fix:

`AimController.log_only()` called `self.backend.send_relative_move(sx, sy)`.
`ChainedBackend` forwarded that call to every backend, including the real
`Win32APIBackend` created by `run_real.py`. Therefore paused (ESC), stopped
(F12), or kill-switch-unavailable frames could still move the real mouse while
reporting `applied_mouse=False`.

Safe pre-fix reproduction with a custom handler:

```text
real_handler_calls_after_log_only= [(24, 0)]
```

Fix applied:

```text
cv_agent/control/base.py       add log_relative_move(), default no-op
cv_agent/control/mouse.py      log_only() uses log_relative_move()
cv_agent/control/backends/csv_logger.py  writes log_relative_move() to CSV
cv_agent/control/backends/chained.py     skips supports_real_output children
```

Post-fix verification:

```text
real_handler_calls_after_log_only= []
csv_rows= 2
tests/test_control_safety.py: 13 passed
full suite: 77 passed
stopped and paused loop tests: CSV row written, zero real handler calls
```

The owner reports physical ESC/F12 validation passed. `test_polling_fallback_toggles_pause_and_stops`
also passes: simulated ESC toggles pause, simulated F12 sets `stopped=True`.

This was a stop-path safety defect, not an accuracy issue. The active
`apply_correction()` path is unchanged and still sends real output when the kill
switch is available and not paused.

## R3. Privacy and release material — PASS

No token/credential/private-key pattern was found in tracked text.

Observed tracked release hazards:

```text
runs/eval/pilot_v0_onnx.console.log
  absolute local paths + GPU model name
runs/pilot_20261114_1920x1080/annotation/manifest.json
  absolute local session paths
runs/pilot_20261114_1920x1080/hard_examples/contact_sheets/*.jpg
  7 tracked 880x460 game-image sheets
```

The project owner reviewed the contact sheets and reports that they contain no
account UI, player names, chat, or other personal content. That closes the
visual-privacy question. The sheets are still excluded from the public
whitelist because they are protected game imagery and are not needed for the
research disclosure.

`test_video.mp4` and weights are ignored, but 113 files under `runs/` are
tracked. A clean clone therefore includes the tracked log, manifests, and
contact sheets unless the release export is allowlisted. The approved
[`RELEASE_WHITELIST.md`](RELEASE_WHITELIST.md) excludes them.

## R4. Licenses and release boundaries — PASS WITH GAPS

- Root `LICENSE` is now MIT, `Copyright (c) 2026 Fligymm`; README states the
  license and excludes weights/data from the MIT grant.
- Installed `ultralytics` 8.4.130 reports **AGPL-3.0**.
- Weights were fine-tuned from a YOLOv8n checkpoint with Ultralytics; weight
  redistribution and AGPL/commercial obligations are unresolved.
- CS2 frames/labels/contact sheets have no recorded redistribution grant.
- Torch BSD-3, OpenCV Apache-2.0, ONNX Runtime GPU MIT, NumPy BSD-3 were
  confirmed from package metadata.

The owner selected **MIT** for project code/documentation,
`Copyright (c) 2026 Fligymm` ([`LICENSE`](../LICENSE)). MIT does not cover
Ultralytics, the derived weights, CS2 captures/labels, or other third-party
material; the scope notice is [`RIGHTS.md`](../RIGHTS.md). The owner authorized
a **whitelist-only research disclosure** and supplied the legal/ethics risk
position; it is recorded in [`LEGAL_AND_ETHICS.md`](LEGAL_AND_ETHICS.md) and is
not a legal opinion or an automatic safe harbor. The whitelist excludes code,
weights, raw data, contact sheets, and local logs:
[`RELEASE_WHITELIST.md`](RELEASE_WHITELIST.md).

Do not upload even the whitelist until the sanitized export, destination, and
visibility are confirmed. The MIT license text must travel with the code/docs;
weights and raw data remain outside the whitelist.

## Decision

Model freeze remains valid. The `log_only` stop path is fixed and covered by
regression tests; the owner reports physical ESC/F12 validation passed. Real
control may be used only through the explicit `run_real.py` path with the kill
switch active. The owner authorized a whitelist-only research disclosure; it was
published to `release/research-whitelist` at commit `bdca2e5`, without touching
`main`, and model weights/raw data remain excluded. The project is
academic/research-only; see
[`ACADEMIC_USE_NOTICE.md`](ACADEMIC_USE_NOTICE.md) and
[`LEGAL_AND_ETHICS.md`](LEGAL_AND_ETHICS.md).