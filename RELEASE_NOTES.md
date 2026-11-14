# Release notes — 2026-11-14

This is the first owner-authorized research disclosure for
`cs2_multitarget_ft_v1`.

## Package scope

Documentation and aggregate evidence only. No code, weights, raw data, labels,
game images, contact sheets, or local logs.

## License

Project code and documentation are MIT-licensed:
`Copyright (c) 2026 Fligymm`. See `LICENSE` and `RIGHTS.md`. MIT does not cover
the model weights, game captures/labels, or third-party assets; these remain
excluded.

## Safety status

- The R2 `log_only` stop-path defect is fixed and regression-tested; the source
  project owner reports physical ESC/F12 validation passed.
- This package does not include the real-control implementation or entrypoint.

## Verification

- File list: `docs/RELEASE_WHITELIST.md`
- Package hashes: `MANIFEST.sha256`
- No absolute local paths, secrets, images, weights, or logs were found in the
  sanitized export at build time.

## Not included

- Code, tools, and tests.
- `best.onnx`, `best.pt`, `yolov8n.pt`.
- Raw captures, frames, videos, labels, and contact sheets.
- Local logs and machine-specific manifests.
