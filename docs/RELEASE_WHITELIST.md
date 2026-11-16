# Research disclosure whitelist

Status: **owner-authorized whitelist; published to `release/research-whitelist`**  
Date: 2026-11-14  
Remote commit: `bdca2e5`; `main` was not pushed.

This is a research/defense disclosure, not a turnkey tool release. The whitelist
deliberately excludes code, real-time aim execution, model weights, raw data,
and identifying material.

## Include (documentation and aggregate evidence only)

```text
LICENSE                                        # MIT, Copyright (c) 2026 Fligymm
THIRD_PARTY_NOTICES.md                         # dependency and weight-scope notes
README.md                                      # sanitized copy, no local absolute paths
RIGHTS.md                                      # MIT scope/research-use notice
docs/ACADEMIC_USE_NOTICE.md
docs/LEGAL_AND_ETHICS.md
docs/LICENSE_REVIEW.md
docs/OPEN_SOURCE_CHECKLIST.md
docs/RELEASE_WHITELIST.md
docs/FINAL_RISK_REVIEW_2026-11-14.md
docs/PROJECT_ROADMAP.md
runs/detect/cs2_multitarget_ft_v1/MODEL_CARD.md
runs/detect/cs2_multitarget_ft_v1/MODEL_MANIFEST.json
runs/pilot_20261115_multitarget/DATASET_CARD.md
runs/pilot_20261115_multitarget/DEVIATIONS.md
runs/pilot_20261115_multitarget/FINETUNE_EVAL.md
runs/pilot_20261115_multitarget/TRAINING_RECORD.md
runs/pilot_20261115_multitarget/README.md
runs/eval/replay_v1_vs_v0/REPLAY_REVIEW.md
```

Code, tests, tools, scripts, notebooks, and model weights are deliberately not
in this first disclosure. A code release would require a separate dual-use and
license decision.

The export must replace any local absolute path with a placeholder such as
`<repo>` or a relative `runs/...` path. Do not copy `.git`, `.venv`, caches, or
local logs.

## Exclude

```text
run_real.py
cv_agent/control/                             # real-time control/aim execution
vision/stream/realtime_loop.py
vision/stream/safety.py                       # keep local; do not ship control hook
model weights (*.pt, *.onnx)
raw captures, frames, videos
contact_sheets/*.jpg
annotation images and labels
runs/eval/*.log
test_video.mp4
yolov8n.pt
```

## Why these exclusions

- Real-control code is dual-use and is not needed to describe the perception
  research or defense evaluation.
- Weights are derived from an Ultralytics YOLO checkpoint; AGPL/commercial
  distribution is unresolved.
- CS2 frames/labels are protected game material; the owner confirmed the
  existing contact sheets contain no account UI, player names, or chat, but that
  is a privacy finding, not a distribution permission.
- Logs and manifests can expose local paths and machine details.

## Publication gate

Published as a separate orphan branch after:

1. MIT with `Copyright (c) 2026 Fligymm` was selected for code/documentation;
2. the sanitized export was checked for absolute paths and secrets (build-time
   scan recorded in [`RELEASE_BUILD_RECORD.md`](RELEASE_BUILD_RECORD.md));
3. the file list was reviewed;
4. the destination/visibility was selected.

Future updates must publish only this whitelist on the release branch/package;
never push the full working tree, because it contains tracked `runs/` images,
logs, and local manifests.