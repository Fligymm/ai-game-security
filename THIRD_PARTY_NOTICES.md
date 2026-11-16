# Third-party notices

This file records the dependency licenses known at build time. It is not legal
advice and does not replace the upstream license texts.

The project's own code and documentation are MIT-licensed
(`Copyright (c) 2026 Fligymm`). Third-party components remain under their own
terms.

| Component | Version | License metadata |
|---|---:|---|
| Ultralytics | 8.4.130 | AGPL-3.0 |
| PyTorch | 2.5.1+cu121 | BSD-3-Clause |
| OpenCV Python | 4.10.0.84 | Apache-2.0 |
| ONNX Runtime GPU | 1.23.2 | MIT |
| NumPy | 2.x | BSD-3-Clause |
| Supervision | 0.30.2 | no license field in installed metadata; verify upstream |

## Important scope note

The model weights are derived from a YOLOv8n checkpoint produced with
Ultralytics. They are **not** MIT-licensed by this project and are excluded from
the whitelist. Do not redistribute weights until the Ultralytics AGPL/commercial
question is resolved.

CS2 game frames, screenshots, contact sheets, and labels are also excluded; the
project cannot grant rights to them.

See [`LICENSE`](LICENSE), [`RIGHTS.md`](RIGHTS.md), and
[`docs/LICENSE_REVIEW.md`](docs/LICENSE_REVIEW.md).