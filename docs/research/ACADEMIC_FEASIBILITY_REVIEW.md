# FPS Game Anti-Cheat Research Project — Academic Feasibility Review

Date: 2026-11-15  
Reviewer role: CV / ML / game security / behavioral time-series / experimental design  
Scope: research feasibility, experimental credibility, publication fit. This is not a code review.
Constraints: read-only review; no model, data, configuration, or business-code changes.

---

## 1. Executive Summary

**Verdict: promising applied project, but not yet a publishable anti-cheat study.**

The project has a genuinely completed and well-documented **target-detection** component:

- frozen `cs2_multitarget_ft_v1`;
- 90-frame external test: mAP50 0.919, head mAP50 0.922, head R@0.35 0.780;
- session-level split, manifest, model card, replay review, rollback model.

The **anti-cheat behavior** component is much less mature than the project description
suggests. There is an existing `RandomForest` baseline and a 250-session proxy dataset,
but:

- the “human” data was captured in a **tkinter 2D target-clicking task**, not FPS aim;
- “bot_agent” is a **straight constant-speed generator**;
- “synthetic” is a **hand-built synthetic trajectory generator**;
- none of these are real FPS players, game bots, or real cheaters;
- the 0.9996 OOF ROC-AUC on this data is a **proxy/generator-separation result**, not
  anti-cheat detection accuracy;
- visual frames and behavior trajectories are **not aligned** in the current experiments.

Therefore:

- **Employment value:** high, especially for CV/ML/data/security engineering roles.
- **Undergraduate thesis:** viable, if the claim is reframed honestly.
- **Journal publication:** not ready now. A modest applied paper becomes plausible only
  after real FPS behavior data, visual-behavior alignment, and a proper held-out benchmark.
- **Anti-cheat claim:** currently a proxy study, not evidence that the system detects
  real aim assistance.

The single most important gap is not model architecture. It is **data semantics and
visual-behavior grounding**.

---

## 2. Current Project Status

| Area | Status | Evidence | Assessment |
|---|---|---|---|
| Target detection model | Complete / frozen | `MODEL_CARD.md`, `FINETUNE_EVAL.md`, `MODEL_MANIFEST.json` | Strongest part of the project |
| Detection dataset | Frozen | 150 frames, 515 boxes, 3 sessions; 90-frame external test | Small but well documented |
| Detection evaluation | Complete | old/new ONNX comparison; per-scene; empty FP; replay | Directional, not statistical proof |
| Behavior dataset | Proxy only | 50 human / 100 bot / 100 synthetic | Not FPS behavior |
| Behavior features | Implemented | `cv_agent/analytics/features.py`, `anticheat/statistical` | Useful baseline, not validated |
| Behavior detector | Exists | `models/baseline_detector.joblib`; `datasets/evaluation_report.json` | OOF 0.9996; likely shortcut-driven |
| Visual-behavior alignment | Not implemented | No joint dataset/report | Critical missing link |
| Sequence model | Not implemented | empty `anticheat/sequence_models` | Not required yet |
| Robustness / humanization | Not implemented | no experiment | Needed for anti-cheat claim |
| Reproducibility / safety | Good | manifests, tests, model card, release whitelist | Above-average for undergrad |

**Direct answer to the central question:**

> The project is **not** a completed anti-cheat research platform. It is a completed
> target-detection project plus a preliminary, proxy-based behavior-classification
> prototype.

That is a good foundation, but the anti-cheat research question remains open.

---

## 3. Existing Research Assets

### 3.1 Detection assets

```text
model             cs2_multitarget_ft_v1
classes           0 enemy_head, 1 enemy_body
input             320x320 ROI, imgsz=640
train             150 frames, 3 sessions/scenes
external test     90 frames, never trained
test mAP50        0.919
head mAP50        0.922
head R@0.35       0.780
empty FP          0/6
replay            8,863 sampled frames, old vs new ONNX
```

Evidence:

- [`MODEL_CARD.md`](../../runs/detect/cs2_multitarget_ft_v1/MODEL_CARD.md)
- [`DATASET_CARD.md`](../../runs/pilot_20261115_multitarget/DATASET_CARD.md)
- [`FINETUNE_EVAL.md`](../../runs/pilot_20261115_multitarget/FINETUNE_EVAL.md)
- [`TRAINING_RECORD.md`](../../runs/pilot_20261115_multitarget/TRAINING_RECORD.md)
- [`REPLAY_REVIEW.md`](../../runs/eval/replay_v1_vs_v0/REPLAY_REVIEW.md)

The detection work is honest about its limits: 90 test frames, one game, three scenes,
one validation scene, recall-oriented body trade-off, and no general background
guarantee.

### 3.2 Behavior assets

```text
datasets/human/         50 sessions
datasets/bot_agent/    100 sessions
datasets/synthetic/    100 sessions
features                15 per session
baseline                RandomForest / IsolationForest
OOF ROC-AUC             0.9996
OOF PR-AUC              0.9987
```

Evidence:

- [`features.py`](../../cv_agent/analytics/features.py)
- [`statistical/__init__.py`](../../anticheat/statistical/__init__.py)
- [`train_baseline_detector.py`](../../tools/train_baseline_detector.py)
- [`evaluation_report.json`](../../datasets/evaluation_report.json)

The existence of this baseline means the development draft’s statement “no detector”
is factually incomplete. The correct statement is:

> A proxy baseline exists, but it has not been validated as FPS anti-cheat detection.

### 3.3 Visual assets

- 53,436 frames from three CS2 scenes;
- 90-frame annotated test;
- 8,863-frame replay comparison;
- 320×320 ROI pipeline and detector/tracker code.

These assets are useful for detection research. They are **not** currently linked to
the behavior trajectories.

---

## 4. Dataset and Label Quality

### 4.1 Detection dataset

Strengths:

- human annotations, not model labels;
- session-level train/val split;
- test is external and has no hash/session overlap;
- empty-frame deviation is documented rather than hidden;
- model card and manifest record provenance.

Limits:

- only 3 sessions and 3 scenes;
- validation covers only `fast_strafe`;
- 90-frame external test is small;
- no cross-map, cross-weapon, cross-resolution, or cross-UI experiment;
- no confidence intervals or repeated splits.

This is enough for a **small applied detection study**, not for a broad generalization
claim.

### 4.2 Behavior dataset — the main problem

The behavior data is not what the project title implies.

| Source | How it was made | What it represents |
|---|---|---|
| `human` | `tools/capture_human.py`: tkinter canvas, move mouse and click a circle | 2D pointing behavior on a desktop UI |
| `bot_agent` | `MechanicalBotAgent`: straight line at constant speed | A deterministic synthetic baseline |
| `synthetic` | `SyntheticAgent`: minimum-jerk, tremor, correction, pause | A hand-designed “human-like” generator |

Consequences:

1. **No FPS aim behavior.** There is no camera control, recoil, strafing, target
   switching in 3D, peeking, pre-aim, or game-sensitivity effect.
2. **No actual game bot.** `bot_agent` is a geometric line generator.
3. **No real cheater.** `CV Agent` must not be equated with a cheater; the project has
   not recorded real assisted-aim users.
4. **No visual-behavior pairing.** The behavior sessions are not the same sessions as
   the CS2 frames.
5. **No scene/map labels or recording-quality variation** in the behavior dataset.

### 4.3 Shortcut evidence

The timing distributions alone are strongly source-specific:

```text
human:     601 points, median dt ≈ 0.00103 s, initial gap ≈ 1.189 s
bot:        31 points, median dt ≈ 0.00827 s, reaction time 0
synthetic: 130 points, median dt ≈ 0.00833 s, reaction time ≈ 0.185 s
```

`reaction_time_ms`, `zero_speed_fraction`, `speed_mean`, `jerk`, and spectral features
can separate the generators without learning anything about FPS cheating. The 0.9996
OOF AUC is therefore **not evidence of anti-cheat capability**.

### 4.4 Leakage assessment

Detection:

- fixed session-level split;
- image hash overlap checked;
- external test not copied into training;
- **no evidence of frame-level leakage found**.

Behavior:

- each row is a session, so window-level leakage is not present;
- but `StratifiedKFold(shuffle=True)` is a random session split with no held-out test;
- the IsolationForest is fit on all human sessions before cross-validation, so its
  anomaly score is not fold-clean;
- no scene/source-grouped or cross-generator generalization test;
- no independent final test.

**Conclusion:** behavior results are OOF proxy results, not an independent validation.

### 4.5 What the data can support

Current behavior data can support:

- a pilot study of “human 2D pointing vs synthetic generators”;
- feature-distribution analysis;
- a negative/limitation paper about proxy data;
- a methods pilot for a future FPS study.

It cannot support:

- “detects aim assistance in FPS games”;
- “detects real cheaters”;
- “generalizes across maps/players”;
- “0.9996 anti-cheat accuracy”.

---

## 5. Methodology Assessment

### 5.1 Target detection

The fine-tuning and evaluation design is appropriate for an applied project:

- old/new model on the same external test;
- per-scene breakdown;
- empty-frame false positives reported;
- replay comparison without new capture;
- limitations and rollback documented.

Weakness: one 90-frame test, three sessions, no confidence intervals, no cross-domain
split. The test has already been used once for model selection, which is acceptable, but
it cannot be reused repeatedly for further tuning.

### 5.2 Behavior classification

The current baseline is a reasonable first step:

- 15 interpretable kinematic/spectral features;
- RandomForest with class balancing;
- OOF metrics;
- feature importance.

But the experiment does not answer the anti-cheat question because:

- labels are generator identity, not cheating;
- no real FPS data;
- no visual grounding;
- no held-out test;
- no sample-rate normalization;
- no false-positive operating point;
- no humanization/adversarial test.

A sequence model is **not** the first priority. The first priority is data validity.
LSTM/GRU/Transformer on this proxy data would produce a more complex but equally
unconvincing result.

### 5.3 Visual-behavior link

The frozen detector provides target boxes, but the project does not currently:

- associate detections to tracks over time;
- extract target acquisition, target switch, tracking error, or aim-event features;
- align detection timestamps with mouse/input timestamps;
- compare behavior features computed from video vs from input.

This is the missing bridge between the strong detection asset and the weak behavior
asset.

---

## 6. Experimental Validity

| Criterion | Detection | Behavior | Comment |
|---|---|---|---|
| Independent train/test | Yes | No (OOF only) | Behavior needs a held-out test |
| Session-level split | Yes | Random session split | No scene/source holdout |
| Baseline comparison | Old vs new ONNX | RandomForest vs IsolationForest | No dummy/Logistic baseline reported |
| Feature ablation | No | No | Needed for behavior claims |
| Cross-scene/map | No | No | Major generalization gap |
| Visual-quality perturbation | No | No | Needed for screen-only claim |
| False-positive rate | Empty-frame only | Not reported at fixed FPR | Anti-cheat needs FPR |
| Precision/Recall/F1 | Yes for detection | Classification report only | Behavior lacks PR curve/operating point |
| Statistical reliability | Small 90-frame test | Small 250-session proxy | No CI/bootstrap |
| Reproducibility | Good | Partial | Behavior lacks split manifest/data card |

**Assessment:** detection experiments are credible but narrow; behavior experiments are
a pilot, not a validation.

---

## 7. Research Novelty Assessment

### What is not novel

- fine-tuning YOLOv8 on a small game dataset;
- RandomForest on kinematic features;
- “human vs bot” classification on synthetic trajectories;
- a high AUC on proxy data.

These are engineering combinations or pilot results.

### Potentially publishable directions

1. **Screen-only, visually grounded aim-behavior analysis**  
   Use the frozen detector and tracker to derive target-acquisition and aim events from
   video, then combine them with trajectory features — without memory reading or game
   process access. This is a meaningful security constraint.

2. **Cross-session and cross-scene robustness**  
   Evaluate whether behavior features survive new maps, weapons, sensitivities, frame
   rates, compression levels, and recording conditions.

3. **Human vs game bot vs CV-agent differential study**  
   Not “cheater detection”, but a controlled study of how different agents differ in
   target acquisition, correction, overshoot, and timing. This is honest and useful.

4. **Benchmark and negative results**  
   A well-documented benchmark showing that proxy data overestimates anti-cheat
   performance would be a legitimate contribution if the real-data experiment is added.

### Novelty verdict

Current novelty is **low**. After real FPS data and visual alignment, the novelty can
become **moderate applied research**, but not a new general theory. That is sufficient
for an undergraduate applied paper if the evaluation is solid.

---

## 8. Academic Publication Feasibility

The following is a readiness assessment, not an acceptance probability. Journal
indexing and current scope must be verified against official databases before submission.

### 8.1 Domestic journals

| Level / example | Current readiness | Main gap | Minimum work | Realistic path |
|---|---|---|---|---|
| Ordinary formal journal (e.g. applied CS/security) | Low–medium | Anti-cheat claim not supported; detection paper small | Reframe as detection/benchmark; add real held-out evaluation | Possible after P0/P1, not now |
| 中国科技核心 (e.g. 《计算机工程与应用》《计算机应用》《计算机应用研究》) | Low | Small data; limited novelty; no statistical tests | Real FPS data, cross-session benchmark, baselines, ablation | Medium after P0/P1 |
| 北大核心 / CSCD | Low | Need stronger method/evaluation and broader comparison | Above plus cross-map robustness and deeper analysis | Low–medium after substantial work |
| 《信息网络安全》《信息安全研究》 | Low | Security claim currently proxy-only | Real threat model, FPS data, FPR/analysis | Low–medium after P0 |

The listed journals are plausible **directions**, not confirmed fits. Verify scope,
review policy, and indexing before submission.

### 8.2 International journals

| Level / example | Current readiness | Main gap | Minimum work | Realistic path |
|---|---|---|---|---|
| PeerJ Computer Science | Low | Needs a complete applied study with real data | P0 + English writing + broader evaluation | Low–medium after P0/P1 |
| Journal of Cybersecurity and Privacy | Low | Security scope but proxy data is insufficient | Real FPS behavior benchmark and threat model | Low–medium after P0 |
| International Journal of Computers and Applications | Low | Broad scope; needs stronger validation | P0 + comparison + writing | Low–medium after P0/P1 |
| Scopus-indexed venue | Low | Indexing/quality varies; needs solid benchmark | P0/P1 | Possible after P0 |
| ESCI | Low | Requires stronger contribution and evaluation | P1 + cross-scene robustness | Low now |
| SCIE | Very low | Not competitive with 90-frame/single-game proxy study | New dataset, method, extensive comparison | Not near-term |

**Recommendation:** do not target SCIE/ESCI first. Build a solid applied paper for a
domestic computer-application/security journal or an open-access Scopus/ESCI venue
after P0. Also consider a workshop/short paper for early feedback.

### 8.3 Two possible papers

**Paper A — detection engineering (closest to current state):**

> “Fine-tuning a lightweight detector for multi-target FPS ROI detection: a small
> external evaluation and failure analysis.”

This is realistic only as a short/applied paper; novelty is limited and the 90-frame
test is a major weakness. It should not claim anti-cheat detection.

**Paper B — anti-cheat behavior benchmark (recommended):**

> “Screen-only aim-behavior benchmark: do visual target-acquisition and trajectory
> features separate humans, game bots, and CV agents across sessions?”

This requires real FPS data and visual alignment, but is a stronger and more honest
contribution.

---

## 9. Critical Gaps

| ID | Severity | Gap | Evidence | Impact | Minimum fix |
|---|---|---|---|---|---|
| G1 | **BLOCKER** | Behavior data is not FPS aim | `capture_human.py` uses tkinter target clicking; bot/synthetic are generators | Core anti-cheat conclusion invalid | Capture real FPS human/bot/CV-agent trajectories |
| G2 | **BLOCKER** | No visual-behavior alignment | Behavior dataset and CS2 frames are separate; no joint manifest | Cannot claim visual behavior detection | Align detector/tracker events with input timestamps; build joint sessions |
| G3 | **BLOCKER** | No independent behavior test | `evaluation_report.json` is OOF only; no held-out test | 0.9996 AUC is not validated | Session/scene-held-out test with frozen protocol |
| G4 | **HIGH** | Label semantics conflate agents | human/bot_agent/synthetic labels are generator identity | “Cheater detection” claim is unsupported | Define human / game bot / CV agent / real cheat separately; do not equate CV agent with cheater |
| G5 | **HIGH** | Sampling/timing shortcuts | human median dt 1.0 ms vs bot/synthetic 8.3 ms; reaction time 0 vs 3.58 s | Model may learn generator, not behavior | Resample, remove timing shortcut features, ablate |
| G6 | **HIGH** | Detection test is narrow | 90 frames, 3 scenes, one game | Limits generalization and journal level | Add sessions/maps; report CI; keep new test untouched |
| G7 | **MEDIUM** | No calibration/FPR/PR operating point | behavior report lacks fixed-FPR metrics | Not usable for anti-cheat risk analysis | Add ROC/PR, TPR@FPR=1%, ECE, bootstrap CI |
| G8 | **MEDIUM** | No feature/ablation study | no behavior ablation | Weak methodological contribution | Ablate kinematic/spectral/event features |
| G9 | **MEDIUM** | No behavior data card/provenance | only `features.json` and JSONs | Reproducibility and review risk | Add dataset card, split manifest, generation scripts/versions |
| G10 | **LOW / resolved in draft v0.2** | v0.1 draft said “no detector” | existing `baseline_detector.joblib`; v0.2 now records it as proxy baseline | Documentation inconsistency | Draft v0.2 corrected; no model change |
| G11 | **ACCEPTED LIMITATION** | Frozen detector body precision trade-off; 90-frame test | documented in model card | Limits claims but accepted | Report as limitation; do not retrain for paper |

G1–G3 are genuine blockers for an **anti-cheat paper**. G1–G3 do not invalidate a
**target-detection paper**, which can be written separately with narrower claims.

---

## 10. Recommended Development Roadmap

### P0 — required before any anti-cheat claim

| ID | Work | Problem solved | Necessity | Expected research gain | Cost | Priority | Affects submission |
|---|---|---|---|---|---|---|---|
| P0-1 | Real FPS behavior capture: human, built-in bot, CV agent, 3+ scenes/maps, 20+ sessions per class | G1, G4, G5 | Essential | Makes the core question testable | High | P0 | Yes |
| P0-2 | Visual-behavior alignment: detector + tracker events joined to input/time | G2 | Essential | Enables “visual behavior” claim | High | P0 | Yes |
| P0-3 | Protocol redesign: session/scene-held-out test, resampling, split manifest | G3, G5 | Essential | Credible metrics rather than OOF | Medium | P0 | Yes |
| P0-4 | Threat-model/label definition: human vs game bot vs CV agent vs real cheat | G4 | Essential | Prevents overclaim and reviewer rejection | Low | P0 | Yes |
| P0-5 | Baseline + ablation: dummy, logistic, tree; feature groups; fixed FPR | G7, G8 | Essential | Establishes a defensible comparison | Medium | P0 | Yes |

Minimum P0 package: **P0-1 + P0-2 + P0-3 + P0-4**. P0-5 can reuse the existing
RandomForest code but must be rerun on the new protocol.

### P1 — strengthens the paper

| ID | Work | Gain | Cost | Priority | Affects submission |
|---|---|---|---|---|---|
| P1-1 | Cross-map/scene and recording-quality perturbation | Robustness evidence | Medium | P1 | Yes |
| P1-2 | Humanization/evasion test (smoothing, delay, jitter) | Avoid brittle claims | Medium | P1 | Yes |
| P1-3 | Sequence model only if feature baseline is insufficient | Method comparison | Medium | P1 | Optional |
| P1-4 | Calibration, bootstrap CI, error analysis | Statistical credibility | Low | P1 | Yes |
| P1-5 | Behavior dataset card + reproducible generation | Reviewability | Low | P1 | Yes |

### P2 — optional, not required for initial submission

- multimodal late fusion;
- larger model/ensemble;
- analyst workflow/shadow mode;
- cross-game generalization;
- deployment.

Do **not** make a complete anti-cheat product, real-time control, auto-ban, or
driver-level detection part of the paper.

### Timeline

```text
P0-1/P0-2  real capture + alignment       4–6 weeks
P0-3/P0-4/P0-5 protocol + baseline       2–3 weeks
P1 robustness + writing                  3–4 weeks
total                                    9–13 weeks
```

The current assets can shorten P0-5, not P0-1/P0-2.

---

## 11. Recommended Journal Shortlist

Indexing status is **not asserted here**; verify on official journal sites and the
latest Chinese/Scopus/WoS master lists.

### First choice (after P0)

1. 《计算机工程与应用》 — applied CS, system/experiment papers; fit if the paper is a
   clear benchmark/application. Verify current scope and review requirements.
2. 《计算机应用》 — applied computer applications; similar fit, competitive.
3. 《计算机应用研究》 — applied research; requires stronger experimental breadth.
4. 《信息网络安全》 / 《信息安全研究》 — security fit; only after real FPS behavior
   data and a credible threat model.

### International (after P0/P1)

1. **PeerJ Computer Science** — broad open-access; requires a complete applied study;
   verify APC and indexing.
2. **Journal of Cybersecurity and Privacy** — scope fit for security/privacy; verify
   current indexing, APC, and review scope.
3. **International Journal of Computers and Applications** — broad applications;
   verify scope and indexing.
4. A Scopus-indexed security/CV workshop or conference — good for early feedback and
   a shorter cycle; verify venue quality.

### Not recommended now

- SCIE/ESCI as a first target;
- top-tier CV/security venues;
- any journal requiring “real cheater detection” unless P0-1 is completed.

---

## 12. Employment Value Assessment

### Strong points for a resume

- end-to-end CV pipeline: capture → detection → tracking → evaluation;
- YOLOv8 fine-tuning, ONNX deployment, fixed test protocol;
- data curation, annotation, deduplication, session-level split;
- reproducible manifests, model card, rollback, tests;
- safety engineering: dry-run, kill switch, regression tests;
- honest documentation of limitations.

### Weak points if described as anti-cheat

- no real FPS behavior data;
- no real cheater labels;
- proxy-only 0.9996 AUC;
- no visual-behavior alignment.

### Recommended resume framing now

> “Offline FPS visual perception and safety-control research platform; YOLOv8n
> multi-target detection with ONNX deployment and reproducible evaluation.”

Do **not** write:

> “anti-cheat detection system with 99.9% accuracy.”

After P0, a stronger resume line becomes defensible:

> “Built a screen-only aim-behavior benchmark with real FPS sessions, visual-behavior
> alignment, and session-held-out evaluation.”

### Employment verdict

- **CV/ML engineer:** strong.
- **Data/algorithm engineer:** strong.
- **Game security/anti-cheat:** promising but currently proxy-level; P0 is needed.
- **Research-oriented roles:** good foundation, but publication needs P0/P1.

---

## 13. Final Verdict

### Is the project worth continuing?

**Yes — but reframe it.** The target-detection and data-engineering work is solid.
The anti-cheat behavior study is a pilot, not a finished result. Continuing is worthwhile
if the next step is real FPS behavior data and visual alignment, not another model.

### Does it have a realistic basis for an undergraduate paper?

**For an undergraduate thesis: yes.**  
**For journal publication now: no.**  
After P0 (real FPS behavior data, visual-behavior alignment, held-out protocol) and P1
(robustness, ablation, calibration), a modest applied paper is realistic. A top-tier
SCIE/ESCI result is not realistic without substantially more data and methodological
depth.

### What is the most valuable innovation direction?

Not another YOLO fine-tune. The strongest direction is:

> **Screen-only, visually grounded aim-behavior benchmark across sessions/scenes, with
> explicit separation of human, game bot, and CV-agent behavior and honest robustness
> analysis.**

The second strongest is:

> **Cross-session/map robustness of visual target-acquisition features under recording
> quality changes.**

### What is the minimum additional work?

1. Real FPS human/bot/CV-agent trajectories in independent sessions (P0-1).
2. Visual-behavior alignment using the frozen detector + tracker (P0-2).
3. Session/scene-held-out benchmark with resampling and split manifest (P0-3).
4. Clear label/threat model; no “CV agent = cheater” conflation (P0-4).
5. Defensible baseline and ablation at fixed FPR (P0-5).

### Domestic vs international priority

- **Domestic first:** applied CS/security journals such as 《计算机工程与应用》,
  《计算机应用》, 《信息网络安全》 — after P0/P1 and with verified scope.
- **International second:** PeerJ CS, Journal of Cybersecurity and Privacy, IJCA, or a
  reputable Scopus workshop — after additional validation and English writing.
- **SCIE/ESCI:** not a first target.

### What can be kept without redoing?

Keep and reuse:

- frozen `cs2_multitarget_ft_v1` and its 90-frame evaluation;
- 150-frame detection dataset, model card, manifest, replay review;
- detector/tracker code and ROI pipeline;
- safety/reproducibility practices and release discipline;
- feature extraction and baseline code as a starting point.

Do not redo:

- target detection training;
- data collection for the detection model;
- the 90-frame test;
- existing model trade-off decisions.

### Overall

**A solid undergraduate CV/security engineering project with a credible detection
component and an early-stage anti-cheat pilot. It is not yet a publishable anti-cheat
study. With 9–13 weeks of P0/P1 work — especially real FPS behavior data and
visual-behavior alignment — it can become a credible applied paper and a stronger
employment artifact without retraining the frozen detector.**

---

## Appendix A — Evidence Index

- [`README.md`](../../README.md)
- [`MODEL_CARD.md`](../../runs/detect/cs2_multitarget_ft_v1/MODEL_CARD.md)
- [`DATASET_CARD.md`](../../runs/pilot_20261115_multitarget/DATASET_CARD.md)
- [`FINETUNE_EVAL.md`](../../runs/pilot_20261115_multitarget/FINETUNE_EVAL.md)
- [`TRAINING_RECORD.md`](../../runs/pilot_20261115_multitarget/TRAINING_RECORD.md)
- [`REPLAY_REVIEW.md`](../../runs/eval/replay_v1_vs_v0/REPLAY_REVIEW.md)
- [`DATA_CONTRACT.md`](../DATA_CONTRACT.md)
- [`ANTICHEAT_DEV_DRAFT.md`](../ANTICHEAT_DEV_DRAFT.md)
- [`features.py`](../../cv_agent/analytics/features.py)
- [`train_baseline_detector.py`](../../tools/train_baseline_detector.py)
- [`capture_human.py`](../../tools/capture_human.py)
- [`mechanical_bot.py`](../../cv_agent/simulation/mechanical_bot.py)
- [`synthetic_agent.py`](../../cv_agent/simulation/synthetic_agent.py)
- [`evaluation_report.json`](../../datasets/evaluation_report.json)

## Appendix B — Evidence Gaps / To Verify

- No behavior dataset card or split manifest found.
- No visual-behavior joint dataset/report found.
- No independent behavior test found.
- No per-session human FPS capture found; `capture_human.py` is a 2D UI task.
- Journal indexing and current scope were not verified online; treat as pending.
- The 0.9996 AUC is from a proxy baseline; its exact leakage status needs a controlled
  re-run before any paper use.