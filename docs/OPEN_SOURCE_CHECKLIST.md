# Open-source release checklist

Status: **owner-authorized research whitelist; not uploaded**  
Target: `cs2_multitarget_ft_v1` and the perception/data tooling.

The approved release shape is the documentation + aggregate-evidence whitelist in
[`RELEASE_WHITELIST.md`](RELEASE_WHITELIST.md). It excludes all code, weights,
raw data, contact sheets, and local logs. A local sanitized archive was built and
scanned; see [`RELEASE_BUILD_RECORD.md`](RELEASE_BUILD_RECORD.md). Do not push
the full working tree.

The project code/documentation license is **MIT**
([`LICENSE`](../LICENSE), `Copyright (c) 2026 Fligymm`). The research whitelist
adds the license and rights notice; weights, raw data, and third-party assets
remain excluded. MIT is permissive and does not enforce the academic/anti-cheat
notice.

## 1. Freeze the technical state

- [x] Model accepted and frozen for this iteration.
- [x] `MODEL_MANIFEST.json` records weights and evidence hashes.
- [x] `MODEL_CARD.md` documents intended use and limitations.
- [x] `DATASET_CARD.md` documents 150-frame ROI dataset.
- [x] `DEVIATIONS.md` records the 11-vs-20 empty-frame deviation.
- [x] `FINETUNE_EVAL.md` records old/new test metrics.
- [x] `REPLAY_REVIEW.md` records the no-new-capture replay review.
- [x] Training config, split manifest, and run records are present.
- [x] `pytest`, compliance, compile, and whitespace checks pass.
- [x] Strict academic-use/prohibition notice added (`docs/ACADEMIC_USE_NOTICE.md`).

## 2. Decide what is published

- [x] Whitelist selected: documentation, model card/manifest, aggregate metrics,
  and the rights notice only.
- [ ] Full codebase: not approved; all code and real-control paths are excluded
  from the first disclosure.
- [ ] Labels + raw manifests: not approved.
- [ ] Model weights (`best.onnx`, `best.pt`) or ONNX only: not approved.
- [ ] Raw CS2 screenshots/videos: not approved.
- [ ] Dataset sample images: not approved.

Recommended default:

```text
publish after decisions: code, docs, labels, manifests, aggregate metrics
review first: model-weight license, sample frames, account/UI pixels
weight file: only ONNX, and only after the Ultralytics license decision
do not publish: raw full-session footage, player names, chat, account UI
```

A clean clone is not automatically a clean release: 113 files under `runs/`
are Git-tracked despite the `runs/` ignore rule. Use an explicit allowlist for
the release export; do not use `git add -A` or assume `.gitignore` removes
 tracked files.

## 3. Licensing

- [x] Code/documentation license selected: **MIT**, `Copyright (c) 2026 Fligymm`
  (`LICENSE`).
- [x] Rights/scope notice added (`RIGHTS.md`); third-party assets and weights are
  explicitly outside the MIT grant.
- [ ] Model weights license selected (weights excluded from this disclosure).
- [ ] Dataset license selected (raw data excluded from this disclosure).
- [x] Third-party licenses reviewed (Ultralytics/YOLO, OpenCV, ONNX Runtime);
  see [`LICENSE_REVIEW.md`](LICENSE_REVIEW.md).
- [x] `THIRD_PARTY_NOTICES.md` records dependency licenses and the
  weight/data scope exclusion.
- [x] README states that the project is research-only and not an anti-cheat product.
- [x] Legal/ethics risk position added (`docs/LEGAL_AND_ETHICS.md`); it is not a
  license or a legal opinion.

Do not assume the Ultralytics model license can be ignored; check it before
publishing weights. Current evidence: no root `LICENSE`, and the installed
`ultralytics` 8.4.130 metadata reports **AGPL-3.0**. See
[`LICENSE_REVIEW.md`](LICENSE_REVIEW.md); the owner must decide the code,
weight, and data licenses separately.

## 4. Scrub and privacy

- [x] Project owner reviewed the existing contact sheets: no account UI,
  player names, chat, or other personal content.
- [ ] Search the final export for local absolute paths, tokens, and usernames.
- [x] Contact sheets are still excluded from the public whitelist because game
  imagery is protected material and not needed for the research disclosure.
- [ ] Confirm no raw capture sessions are committed by accident.
- [x] `.gitignore` excludes weights, videos, and generated runs by default;
  tracked `runs/` files remain a release hazard and are excluded by allowlist.
- [x] Do not publish the local `run_real.py` hook; it is local-only.
- [x] Use [`RELEASE_WHITELIST.md`](RELEASE_WHITELIST.md), not the full tree.

Known tracked release hazards (audit 2026-11-14):

```text
runs/eval/pilot_v0_onnx.console.log
  tracked; contains absolute local paths and GPU model name
runs/pilot_20261114_1920x1080/annotation/manifest.json
  tracked; contains absolute local session paths
runs/pilot_20261114_1920x1080/hard_examples/contact_sheets/*.jpg
  tracked; owner confirms no account/player/chat content; excluded from whitelist
```

Exclude or scrub these from the public export. Do not delete the originals
without an explicit data-retention decision.

## 5. Safety review

- [x] `--apply-mouse` remains explicit and off by default in `realtime_loop`.
- [x] `run_real.py` remains the explicit real-control entry.
- [x] ESC/F12 kill switch is verified; global-hotkey fallback is documented.
- [x] **Real-control stop path verified.** `AimController.log_only()` now uses
  `log_relative_move()`, and `ChainedBackend` skips real-output children.
  Stopped/paused regression tests write CSV and produce zero real handler calls.
  Project owner reports physical ESC/F12 validation passed.
- [x] `ChainedBackend`, CSV `flush()`, and Win32 hook semantics remain compatible;
  the new logging-only method does not change `apply_correction()`.
- [x] README contains the strict academic-use/prohibition notice.
- [x] Do not ship a default that sends mouse input without an explicit flag.
- [x] `run_real.py` remains local-only for this iteration; no sanitized public
  entrypoint is published. Its default path is computed from the repository root,
  not a hardcoded absolute path.

## 6. Reproducibility

- [ ] Fresh clone can install dependencies from `requirements.txt`.
- [ ] Whitelist export uses only relative/placeholder paths; historical docs with
  absolute examples are excluded or sanitized.
- [ ] README commands use portable relative paths.
- [ ] Model card and dataset card links resolve.
- [ ] Evaluation command reproduces the reported JSON schema.
- [ ] Replay tool runs on the documented pilot layout.
- [ ] All required test fixtures are included or documented.

## 7. Release artifacts

Authoritative contents: [`RELEASE_WHITELIST.md`](RELEASE_WHITELIST.md).
The built archive has 21 files: license/notices, documentation, model card and
manifest, dataset/eval/training records, and the replay review.

```text
LICENSE
THIRD_PARTY_NOTICES.md
README.md
RIGHTS.md
RELEASE_NOTES.md
MANIFEST.sha256
docs/{ACADEMIC_USE_NOTICE,LEGAL_AND_ETHICS,LICENSE_REVIEW,OPEN_SOURCE_CHECKLIST,
      RELEASE_WHITELIST,FINAL_RISK_REVIEW_2026-11-14,PROJECT_ROADMAP}.md
runs/detect/cs2_multitarget_ft_v1/{MODEL_CARD.md,MODEL_MANIFEST.json}
runs/pilot_20261115_multitarget/{DATASET_CARD,DEVIATIONS,FINETUNE_EVAL,
      TRAINING_RECORD,README}.md
runs/eval/replay_v1_vs_v0/REPLAY_REVIEW.md
```

Do not include by default:

```text
code, tests, tools, run_real.py
model weights (*.onnx, *.pt)
raw capture MP4s / frames / labels
runs/eval/pilot_v0_onnx.console.log
runs/pilot_20261114_1920x1080/hard_examples/contact_sheets/
annotation manifests containing absolute local paths
test_video.mp4
```

`run_real.py` is local-only and not part of the whitelist. The source default is
computed from the repository root, not a hardcoded absolute path.

## 8. Final gate

- [ ] A second reviewer checks the checklist and final file list.
- [x] The `log_only` real-output blocker is fixed and regression-tested.
- [ ] `git status` contains only intended files.
- [ ] Hashes in `MODEL_MANIFEST.json` match the release weights (weights are not
  in this disclosure).
- [x] Release notes state the 90-frame test size and limitations.
- [ ] Tag the release only after the license, destination, and privacy checks
  pass; MIT is selected for code/docs, weights/data remain excluded.