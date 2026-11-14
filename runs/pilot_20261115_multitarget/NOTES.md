# Multi-target pilot notes

Fill one row per session immediately after F12 and `check_session`.


| session_id                         | scene         | planned | actual duration | frames_recorded | selected_frames | 2–4 heads? | check ok | notes |
| ---------------------------------- | ------------- | ------- | --------------- | --------------- | --------------- | ---------- | -------- | ----- |
| realtime_cs2_agent_20261114_194803 | static_target | 10 min  | 10 min          | 18000           | 8669            | YES        | ok       |       |
| realtime_cs2_agent_20261114_200201 | slow_strafe   | 10 min  | 10 min          | 18000           | 12772           | YES        | ok       |       |
| realtime_cs2_agent_20261114_201336 | fast_strafe   | 10 min  | 10 min          | 18000           | 9116            | YES        | ok       |       |


Environment (same for all sessions):

```text
desktop         = 2560x1440
CS2 window      = 1920x1080 centered
ROI             = 320
DPI             = 1600
sensitivity     = 0.80
FOV             = 90
map / bot setup = Aimbotz
capture mode    = dry_run
```

Acceptance:

- `check_session` `ok=true`, `warnings=[]`
- `frames_recorded >= 15000`
- `selected_frames > 0`
- replay decodable
- at least some sampled positions show 2–4 visible heads

