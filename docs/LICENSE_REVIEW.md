# License and release-rights review

Date: 2026-11-14  
Scope: code, model weights, dataset, and third-party dependencies for
`cs2_multitarget_ft_v1`. This is a factual inventory, not legal advice.

The project is **academic/research-only**; see
[`ACADEMIC_USE_NOTICE.md`](ACADEMIC_USE_NOTICE.md). The code/documentation
license is MIT ([`LICENSE`](../LICENSE)); the academic notice is a separate
ethical/legal statement, not a field-of-use condition of the MIT license.

## Current repository state

```text
root LICENSE                    MIT, Copyright (c) 2026 Fligymm
README license statement        present (MIT; third-party/weights excluded)
model-weight license            not declared; weights excluded from whitelist
dataset license                 not declared; raw data excluded from whitelist
```

The owner selected **MIT** for project code and documentation. This choice does
not relicense Ultralytics, PyTorch, OpenCV, ONNX Runtime, NumPy, the CS2
captures, or the derived model weights. Those remain subject to their own terms
and are excluded from the public whitelist.

## Dependency evidence

From the local virtual environment on 2026-11-14:

| Package | Version | License metadata |
|---|---:|---|
| `ultralytics` | 8.4.130 | **AGPL-3.0** |
| `torch` | 2.5.1+cu121 | BSD-3-Clause |
| `opencv-python` | 4.10.0.84 | Apache 2.0 |
| `onnxruntime-gpu` | 1.23.2 | MIT |
| `numpy` | 2.x | BSD-3-Clause |
| `supervision` | 0.30.2 | no license field in installed metadata |

The important unresolved point is **Ultralytics/YOLO**. The installed package is
AGPL-3.0, and the fine-tuned weights were produced with it from a YOLOv8n
checkpoint. Publishing the code, the training pipeline, or the weights may carry
AGPL obligations or require a commercial Ultralytics license depending on the
distribution model. Do not assume the ONNX file is freely redistributable.

`supervision` has no license field in its installed metadata; confirm its
upstream license before distributing a bundled environment. Version pins in
`requirements.txt` are also broad (`>=`), so a future install may resolve a
different license/version.

## Dataset and game material

The 150-frame multi-target dataset, the 90-frame test set, and the contact
sheets are CS2 screen captures. No written permission or dataset license is
present in the repository.

```text
raw frames / videos          no redistribution grant found
annotation labels            derived from the captured frames; treat as restricted
contact sheets / crops       contain game imagery; treat as restricted
test_video.mp4 (ignored)     local-only reference video; do not publish by default
```

The project can keep these locally for research, but public release requires the
owner to confirm the rights to the game imagery and any people/accounts visible
in it. Do not publish a dataset license or a sample gallery until that is
settled.

## Third-party and game assets

- No Valve/CS2 Workshop asset license is recorded.
- No permission for redistributing CS2 HUD, player names, chat, or account UI is
  recorded.
- The ignored `test_video.mp4` and local `yolov8n.pt` are not part of Git; they
  are still local-only assets.

## Release recommendation

The owner authorized a **whitelist-only research disclosure**: documentation,
model card/manifest, aggregate metrics, and the rights notice only. It does not
include code, weights, raw data, contact sheets, or local logs. See
[`RELEASE_WHITELIST.md`](RELEASE_WHITELIST.md) and
[`LEGAL_AND_ETHICS.md`](LEGAL_AND_ETHICS.md).

The project code/documentation license is MIT:
[`LICENSE`](../LICENSE), `Copyright (c) 2026 Fligymm`. The MIT text is included
in the research whitelist. The owner still needs to decide the model-weight and
dataset distribution model, and the upload destination/visibility.

MIT is permissive and does not contain a field-of-use restriction. The academic
and anti-cheat notice is a separate project statement, not a condition of the
MIT license; illegal use remains prohibited by law.

Allowed: local research use, internal evaluation, MIT-licensed code/doc
redistribution with the license notice, and preparing the sanitized whitelist.
Weights and raw data remain outside the licensed/public scope.

See [`OPEN_SOURCE_CHECKLIST.md`](OPEN_SOURCE_CHECKLIST.md) for the release gate.