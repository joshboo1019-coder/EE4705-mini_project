# Overnight run — STATUS (Student B, 2026-10-04 00:30–10:30 SGT)

Updated at least hourly on `b/overnight-all`. Times are SGT.

## API spend (budget US$2.00, stop API-heavy work at US$1.80)

| Item | Spend (USD) | How counted |
|---|---|---|
| P0 smoke + harness test + baseline S1–S4 + P2a S3 (~45 qwen-flash parser calls, 3 qwen3-vl-flash looks) | ~0.004 | ~1.5k tokens/call × eval/task3_eval.py PRICES |
| P2b runs (2 × S3) + stopsign S3 | ~0.002 | |
| P3 (b/upgrade) evals, incl. Gemini Hard | ~0.386 | eval/upgrade_eval.md spend table |
| e2e S5 dry run + P5 dry run (~25 calls) | ~0.003 | |
| **Total so far** | **~0.40** | updated 02:10 (cap 1.80) |

## Items

| Item | Status | Branch | Notes |
|---|---|---|---|
| P0 merge bonus_b → main | done (by teammate) | main | PR #3 (bonus_b) and PR #4 (fix/task4-color-grounding) were merged by the repo owner at 00:32, before this run started. Tests: same 6 failures as pre-merge main (0c76f79), 95 pass. Mock OK. Real-sim smoke: turn 1.8° off; orange ball `[MISSION] status=SUCCESS` (true d = 0.84 m). Tag `b-task3-merged` → aa77186. 8 branches created from ee9593f. |
| Virtual display | done | – | Xvfb :99 1920×1080 from user-space debs (no sudo); xterm + platform panel + ffmpeg x11grab work. |
| P1 e2e harness + baseline | done 01:11 | b/overnight-all | eval/e2e/results/20261004-0101_baseline: S1 closed max 1.9° (pass), open-loop ~24 % of target, 3 s move 2.24 m; S2 7/7 + turns ≤2.0° + no contact; S3 **3/10 strict** (chairs stop at true 0.84–0.94 m, signs never detected); S4 look 3/3 correct (hand-checked), multi-goal SUCCESS 2/2 but red chair at 0.88 m. Clips ~/Videos/e2e/20261004-0101_baseline/. |
| P2a task4 via main.py | done 01:17 | assist/task4-via-main | `main.py --scenario N`; S3 fully through main.py: 10/10 trials have the LLM [CMD] line; strict 3/10 (same as baseline, nav unchanged). eval/e2e/results/20261004-0111_p2a_task4_via_main |
| P2b C2 margin | done 01:35 | assist/c2-margin | per-class APPROACH_STOP_M (chair 0.56, ball 0.78, default 0.57; FOUND_DISTANCE_M=0.80 kept for C2). S3 strict 3/10 → **6/10**, 0 contacts (v1 single 0.57: 4/10, broke the ball). docs/task4_c2_margin.md; C's own table recounts 6/10 → 1/10 strict. |
| P2c task2 evidence | done 01:26 (agent) | assist/task2-evidence | 108 turn trials (±45/90/180 × closed / A's open / calibrated open), 1 table + 1 figure from JSONL, 6 YOLO screenshots, 10 s annotated onboard clip; 7 inconsistencies in A's numbers documented. |
| P2d CLI/tests | done 01:01 | chore/cli-tests | `--mock`; 104 passed + 1 xfail (recenter-time test, needs C) |
| P2e repro + zip | done 01:16 | chore/repro-zip | README fixed (9 problems), docs/REPRODUCE.md, tools/make_submission_zip.sh (14 MB, 583 files, key scan) |
| P2f stop sign | done; **not merged** | assist/stopsign | detection 7/387 → 228/387, but e2e S3 5/10 vs 6/10 without (chair lost near signs → collision; elevated range uncalibrated). Documented on the branch. |
| P2g Video_Task4 candidates | done 01:37 | – | ~/Videos/candidates/Video_Task4_candidate_{a,b,c}.mp4 (= S3 v2 clips 08/03/07: search→blue chair 0.70 m; green chair among red/blue 0.68 m; orange ball paraphrase 0.60 m) |
| P3 B upgrades | done 02:00 (agent) | b/upgrade | talk-back, repeat/until_see, closed-loop distance_m, bounds, stop fast path, state/status/undo/return_home, prompt v5; Standard v4→v5: qwen 45/45→45/45, nano 43→42, gemini 45→45; Hard (71, held out): qwen 86 %, nano 70 %, gemini 100 %, v4-qwen 83 %; injection: 0 unsafe passed the validator. Regression: noise (typos) 8/8→4/8 on qwen (fix attempt on b/v5-noise). S5 dry run on the real sim 7/7. 250 tests pass on b/overnight-all. |
| P4 integrate + full e2e | final run in progress (02:06) | b/overnight-all | merged: cli-tests, task4-via-main, c2-margin, task2-evidence, repro-zip, b/upgrade (not stopsign): 250 passed + 1 xfail |
| P5 typed demo | dry run OK (282 s, 8 segments) | – | final take after the P4 run |
| P6 documents | in progress | b/overnight-all | TEAM_HANDOFF draft committed; B_code_walkthrough by agent (docs/b-walkthrough) |

| Extra: v5 noise fix | in progress (agent) | b/v5-noise | new held-out noise set first, then a general rule fix; not merged |
| Extra: hard scene (stretch) | in progress (agent) | assist/hard-scene | scene + S6 plumbing offline; recorded S6 later |
