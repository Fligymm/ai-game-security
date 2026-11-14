# Legal and ethics risk position

Status: project risk statement, not legal advice or a guarantee. Consult qualified
counsel and your institution before any publication or formal-server testing.

## Technical distinction

This project uses screen capture, offline/closed-environment inference, and
optional OS-level relative mouse simulation. It does not read game process
memory, hook the game, or modify game/server data in the research path.

That distinction lowers some technical risk; it does **not** create a legal
safe harbor. Academic research is a responsibility/defense factor, not an
automatic exemption.

## Legal risk map

### Criminal law

- **Criminal Law Art. 285(3)** — providing programs/tools used to intrude into or
  illegally control computer information systems. Pure screen-capture + input
  simulation is less likely to meet the "intrusion" element than memory cheats,
  but distributing a usable cheating tool can still be pursued.
- **Criminal Law Art. 286** — damaging computer information systems. Usually not
  met by passive screen capture; becomes relevant if the work bypasses,
  interferes with, or modifies anti-cheat/game processes or data.
- **Criminal Law Art. 217** — copyright infringement, including circumventing
  technological protection measures. Deliberately defeating DRM/anti-capture
  protections for data collection can create risk.

### Administrative law

- **Cybersecurity Law Art. 27** — prohibits illegal intrusion, control,
  interference, or data theft, and providing tools for those activities.
- **Public Security Administration Punishments Law Art. 29** — non-criminal
  interference with computer systems can lead to detention/fines.
- **Generative AI service measures** — training-data provenance and any public
  model/service deployment can add compliance obligations.

### Civil and contractual risk

- **Civil Code Arts. 1165/1167** — fault-based tort and injunctive relief.
- Game EULAs almost universally prohibit automation, aim assistance, scripts,
  and cheats, regardless of whether memory is read. Using a formal account or
  live service can be breach of contract and tort.
- **Copyright Law** — game visuals are protected; bulk capture for training or
  publication can exceed fair use. Art. 24 research/study exceptions are narrow;
  large datasets or published weights are unlikely to qualify automatically.

### Research norms

Responsible security research generally means: prior disclosure/authorization,
closed or vendor-provided test environments, no real-player impact, no bypass of
protections, no release of a ready-to-use cheat, and coordinated disclosure.

## Permitted research boundary for this project

- Purpose: anti-cheat/detection/defense research, not improving cheat efficacy.
- Environment: local offline/closed simulation, or a vendor-authorized test
  server; no formal live account, no real-player matches.
- Acquisition: public OS screen capture only; no memory reads, injection,
  anti-cheat bypass, protocol cracking, or DRM circumvention.
- Data: minimum necessary; no public release of raw footage, labels, or
  identifiable material.
- Output: principles, detection/defense methods, aggregate metrics, model card,
  and limitations. Do not distribute a ready-to-run aim program, weights, or
  automation scripts.
- Disclosure: follow responsible disclosure/VDP practice.

## Red lines

Do not use or distribute this work for:

- live multiplayer cheating or gaining an unfair advantage;
- bypassing or attacking anti-cheat systems;
- unauthorized control of another person's device/account;
- public release of a turnkey cheat, model weights, or raw game datasets;
- surveillance, harassment, or any illegal activity.

## Release posture

The owner has authorized a **whitelist-only research disclosure**, not a
turnkey tool release. The public package should exclude:

```text
real-time control / aim execution code
run_real.py
model weights
raw captures, frames, contact sheets, labels
local logs and absolute paths
```

Project code/documentation is MIT-licensed (`Copyright (c) 2026 Fligymm`), but
MIT does not grant rights to weights, game captures/labels, or third-party
assets. The academic/anti-cheat notice is a separate ethical/legal statement,
not a field-of-use condition of MIT. See [`LICENSE`](../LICENSE),
[`RIGHTS.md`](../RIGHTS.md), [`ACADEMIC_USE_NOTICE.md`](ACADEMIC_USE_NOTICE.md),
and [`LICENSE_REVIEW.md`](LICENSE_REVIEW.md).