# Multi-target data collection

Status: not started.

Follow [`docs/MULTITARGET_DATA_TASKBOOK.md`](../../docs/MULTITARGET_DATA_TASKBOOK.md).

Targets:

- 3 new sessions: `static_target`, `slow_strafe`, `fast_strafe`
- each about 10 minutes, 2–4 visible heads
- 150 annotated frames
- ≥60 frames with 2+ heads
- ≥20 empty frames
- 90-frame pilot test untouched

Outputs:

```text
captures/                 # new sessions
reports/                  # check_session JSON
replays/                  # replay MP4
annotation_multitarget/   # created by sample_multitarget_annotation.py
NOTES.md                  # fill after each session
```