# Overnight run — STATUS (Student B, 2026-10-04 00:30–10:30 SGT)

Updated at least hourly on `b/overnight-all`. Times are SGT.

## API spend (budget US$2.00, stop API-heavy work at US$1.80)

| Item | Spend (USD) | How counted |
|---|---|---|
| P0 smoke + harness test + baseline S1–S4 + P2a S3 (~45 qwen-flash parser calls, 3 qwen3-vl-flash looks) | ~0.004 | ~1.5k tokens/call × eval/task3_eval.py PRICES |
| P3 agent evals (b/upgrade) | see eval/upgrade_eval.md | agent keeps its own running total (cap US$0.90) |
| **Total so far (excl. P3)** | **~0.004** | updated 01:20 |

## Items

| Item | Status | Branch | Notes |
|---|---|---|---|
| P0 merge bonus_b → main | done (by teammate) | main | PR #3 (bonus_b) and PR #4 (fix/task4-color-grounding) were merged by the repo owner at 00:32, before this run started. Tests: same 6 failures as pre-merge main (0c76f79), 95 pass. Mock OK. Real-sim smoke: turn 1.8° off; orange ball `[MISSION] status=SUCCESS` (true d = 0.84 m). Tag `b-task3-merged` → aa77186. 8 branches created from ee9593f. |
| Virtual display | done | – | Xvfb :99 1920×1080 from user-space debs (no sudo); xterm + platform panel + ffmpeg x11grab work. |
| P1 e2e harness + baseline | done 01:11 | b/overnight-all | eval/e2e/results/20261004-0101_baseline: S1 closed max 1.9° (pass), open-loop ~24 % of target, 3 s move 2.24 m; S2 7/7 + turns ≤2.0° + no contact; S3 **3/10 strict** (chairs stop at true 0.84–0.94 m, signs never detected); S4 look 3/3 correct (hand-checked), multi-goal SUCCESS 2/2 but red chair at 0.88 m. Clips ~/Videos/e2e/20261004-0101_baseline/. |
| P2a task4 via main.py | done 01:17 | assist/task4-via-main | `main.py --scenario N`; S3 fully through main.py: 10/10 trials have the LLM [CMD] line; strict 3/10 (same as baseline, nav unchanged). eval/e2e/results/20261004-0111_p2a_task4_via_main |
| P2b C2 margin | after-run in progress | assist/c2-margin | APPROACH_STOP_M=0.57 from 20 before-trials (chairs +0.16 m, ball −0.09 m, p95 0.23 m) |
| P2c task2 evidence | in progress (agent) | assist/task2-evidence | |
| P2d CLI/tests | done 01:01 | chore/cli-tests | `--mock`; 104 passed + 1 xfail (recenter-time test, needs C) |
| P2e repro + zip | done 01:16 | chore/repro-zip | README fixed (9 problems), docs/REPRODUCE.md, tools/make_submission_zip.sh (14 MB, 583 files, key scan) |
| P2f stop sign | in progress (agent) | assist/stopsign | |
| P2g Video_Task4 candidates | queued | – | after P2a, P2b |
| P3 B upgrades | in progress (agent) | b/upgrade | |
| P4 integrate + full e2e | queued | b/overnight-all | |
| P5 typed demo | queued | – | |
| P6 documents | queued | b/overnight-all | |
