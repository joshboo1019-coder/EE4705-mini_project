# Overnight run — STATUS (Student B, 2026-10-04 00:30–10:30 SGT)

Updated at least hourly on `b/overnight-all`. Times are SGT.

## API spend (budget US$2.00, stop API-heavy work at US$1.80)

| Item | Spend (USD) | How counted |
|---|---|---|
| P0 smoke (2 LLM calls, qwen-flash) | ~0.0002 | tokens × eval/task3_eval.py PRICES |
| **Total so far** | **~0.0002** | |

## Items

| Item | Status | Branch | Notes |
|---|---|---|---|
| P0 merge bonus_b → main | done (by teammate) | main | PR #3 (bonus_b) and PR #4 (fix/task4-color-grounding) were merged by the repo owner at 00:32, before this run started. Tests: same 6 failures as pre-merge main (0c76f79), 95 pass. Mock OK. Real-sim smoke: turn 1.8° off; orange ball `[MISSION] status=SUCCESS` (true d = 0.84 m). Tag `b-task3-merged` → aa77186. 8 branches created from ee9593f. |
| Virtual display | done | – | Xvfb :99 1920×1080 from user-space debs (no sudo); xterm + platform panel + ffmpeg x11grab work. |
| P1 e2e harness + baseline | in progress | b/overnight-all | |
| P2a task4 via main.py | queued | assist/task4-via-main | |
| P2b C2 margin | queued | assist/c2-margin | needs P1 S3 logs |
| P2c task2 evidence | in progress (agent) | assist/task2-evidence | |
| P2d CLI/tests | in progress (agent) | chore/cli-tests | |
| P2e repro + zip | in progress (agent) | chore/repro-zip | |
| P2f stop sign | queued (COULD) | assist/stopsign | |
| P2g Video_Task4 candidates | queued | – | after P2a, P2b |
| P3 B upgrades | in progress (agent) | b/upgrade | |
| P4 integrate + full e2e | queued | b/overnight-all | |
| P5 typed demo | queued | – | |
| P6 documents | queued | b/overnight-all | |
