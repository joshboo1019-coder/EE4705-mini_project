# e2e comparison: baseline `20261004-0101_baseline` vs final `20261004-0221_final`

Baseline = merged main (ee9593f) before tonight's changes, with S3 started by the scenarios.py mechanism (main.py had no --scenario yet). Final = `b/overnight-all` (all branches that passed their checks; not `assist/stopsign`). Same harness, fresh launch per scenario, real LLM (qwen-flash), every scenario recorded: clips under `~/Videos/e2e/`. Per-run details: `eval/e2e/results/<run>/summary.md`.

## Final round (2026-10-04 14:20): pre-final vs fix/final

Strict criteria per S3 trial: C1 (target in the live stop frame) + C2 (TRUE planar d ≤ 0.80 m, ground truth from
the trace, logging only) + C3 (`[FOUND]`); scenario 10 = the correct `target_not_found`. Contacts = trace samples
with the robot touching the target / another scene object (F5, logging only). pre-final = tag `pre-final`
(no-GT navigation; runs `20261004-1216_no_gt_height`, `20261004-1337_premerge_gate`); fix/final = F1 + F2 + F3 +
F5 + H1/H2 (runs `20261004-*_fixfinal_s3_r1..r3`, no video).

| # | Target | pre-final (no-GT nav, v5) (n=2) | fix/final (n=3) |
|---|---|---|---|
| 01 | red chair | 1/2 (true d 0.76, 0.21) | 1/3 (true d 0.58, 0.64, 0.62; contact runs target 1, other 0) |
| 02 | orange sports ball | 2/2 (true d 0.67, 0.64) | 3/3 (true d 0.64, 0.67, 0.62; contact runs target 0, other 3) |
| 03 | green chair | 2/2 (true d 0.72, 0.69) | 3/3 (true d 0.67, 0.69, 0.68; contact runs target 0, other 0) |
| 04 | red chair | 1/2 (true d 0.58, 0.68) | 0/3 (true d 0.63, 0.64, 0.61; contact runs target 0, other 0) |
| 05 | yellow stop sign | 0/2 (true d 3.77, 3.78) | 0/3 (true d 3.78, 3.77, 3.78; contact runs target 0, other 0) |
| 06 | green stop sign | 0/2 (true d 5.04, 5.05) | 0/3 (true d 5.05, 5.04, 5.05; contact runs target 0, other 0) |
| 07 | orange sports ball | 2/2 (true d 0.59, 0.64) | 3/3 (true d 0.66, 0.62, 0.65; contact runs target 0, other 0) |
| 08 | blue chair | 2/2 (true d 0.67, 0.62) | 3/3 (true d 0.63, 0.67, 0.65; contact runs target 0, other 0) |
| 09 | red stop sign | 0/2 (true d 1.27, 1.27) | 0/3 (true d 1.27, 1.26, 1.27; contact runs target 0, other 0) |
| 10 | blue chair | 2/2 (true d None, None) | 3/3 (true d None, None, None; contact runs target 0, other 0) |
| | **all** | **12/20** (60 %) | **16/30** (53 %) |

| Class | pre-final (no-GT nav, v5) | fix/final |
|---|---|---|
| chair | strict 6/8; SUCCESS 6 (true d mean/max 0.69/0.76, 0 > 0.80 m); stop_verification 1; contact 1 | strict 7/12; SUCCESS 7 (true d mean/max 0.66/0.69, 0 > 0.80 m); stop_verification 4; contact 1 |
| sports ball | strict 4/4; SUCCESS 4 (true d mean/max 0.64/0.67, 0 > 0.80 m); stop_verification 0; contact 2 | strict 6/6; SUCCESS 6 (true d mean/max 0.64/0.67, 0 > 0.80 m); stop_verification 0; contact 3 |
| stop sign | strict 0/6; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 | strict 0/9; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 |

- **Every SUCCESS stop is within C2** on both sides (fix/final: chairs mean 0.66 m, max 0.69; balls max 0.67).
- The difference is the red chair: scenario 4 fails `stop_verification` 3/3 here (frame-filling chair labelled
  "bed"; the F1 `[VERIFY]` retry ran and did not rescue it), but the F1 gate on the same code had 3/3 (2 rescued by
  `[VERIFY]`), so scenario 4 is 3/6 with F1. F1 only runs after a failed stop check, so it cannot turn a success into
  a failure. n is small: 16/30 vs 12/20 is within noise.
- **Contacts:** scenario 1 r1 touched the target red chair for ~18 s, during the 4th re-acquire strafe and the
  rotating search after it (not at the stop), so no stop-margin change (F5 mitigation not triggered by the stop);
  scenario 2 touches the red stop-sign pole on the straight path to the ball (3/3) — no obstacle avoidance (known
  limitation).

## Summary (per suite)

| Suite | Baseline | Final | Verdict | Why |
|---|---|---|---|---|
| S1 Task 2 | closed max 1.9°, open mean 79.6°, move 2.24 m | closed max 2.0°, open 79.6°, move 2.28 m | **same** | no Task 2 code changed (evidence branch only) |
| S2 Task 3 script a–g | 7/7, turns ≤ 2.0°, no contact | 7/7, turns ≤ 1.8°, no contact (+ `[PLAN]`/`Robot:` talk-back) | **same** (better UX) | v5 keeps every v4 `[CMD]` line; one v5 regression (step e) was found by run `20261004-0206_final` and fixed (`e06968e`) before the definitive run |
| S3 Task 4 (strict: true d ≤ 0.80 m) | **3/10** (n=3: **9/30**) | **5/10** (n=3: **16/30**; 6/10 in the P2b v2 run) | **better** | per-class stop margin (`assist/c2-margin`); every typed goto now goes through `main.py --scenario` with the LLM `[CMD]` |
| S4 bonus | look 3/3; multi-goal 2/2 but red chair at 0.88 m (C2 ✗) | look 3/3; multi-goal 2/2 at 0.69 / 0.58 m (C2 ✓) | **better** | stop margin |
| S5 B upgrades | n/a | 7/7 (8/8 incl. "spin around twice" in the delta run) | **new** | `b/upgrade` |

No branch made a suite worse, so none was reverted from `b/overnight-all`. Per scenario, S3 #4 got worse (the
baseline's "SUCCESS" at 0.84 m became `stop_verification` at 0.57 m: the frame-filling red chair is labelled "bed"
at the stop) and #1 varies between runs (0.74 m ✓ in v2, 1.04 m ✗ in the final after a re-acquire). Excluded:
`assist/stopsign` — S3 **5/10 vs 6/10** without it (run `20261004-0138_stopsign_eval`; chair lost and walked into
in scenario 1), see `docs/task4_stopsign.md`.

**Run history (all committed under `eval/e2e/results/`, clips under `~/Videos/e2e/`):** `0101_baseline` →
`0111_p2a_task4_via_main` (S3 via main.py) → `0118_p2b_c2_margin` (v1: one stop for all classes, broke the ball) →
`0128_p2b_c2_margin_v2` (per class) → `0138_stopsign_eval` (not merged) → `0153_s5_dryrun` → `0206_final`
(**S2 failed: STATE regression**) → `0221_final` (**definitive**) → `0237_final_delta_fixes` (S2 + S5 after the
walkthrough fixes: 7/7, 8/8) → `S6` hard scene (stretch, see below).

## S3 with n = 3 per scenario (added 03:30)

Two more S3 runs on each side (baseline = merged-main code at 32c6f78 with the scenarios.py driver; final =
`b/overnight-all` via `main.py --scenario`), fresh launch each: `0101_baseline` + `0311_baseline_rep2` +
`0324_baseline_rep3` vs `0221_final` + `0304_final_rep2` + `0317_final_rep3` (`eval/e2e/aggregate_s3.py`,
`eval/e2e/S3_n3.md`).

| # | Target | baseline (merged main) (n=3) | final (b/overnight-all) (n=3) |
|---|---|---|---|
| 01 | red chair | 0/3 (true d 0.85, 0.83, 0.83) | 1/3 (true d 1.04, 0.87, 0.77) |
| 02 | orange sports ball | 3/3 (true d 0.66, 0.65, 0.68) | 3/3 (true d 0.69, 0.63, 0.66) |
| 03 | green chair | 0/3 (true d 0.94, 0.98, 0.93) | 3/3 (true d 0.69, 0.7, 0.7) |
| 04 | red chair | 0/3 (true d 0.84, 0.85, 0.88) | 0/3 (true d 0.57, 0.6, 0.6) |
| 05 | yellow stop sign | 0/3 (true d 3.78, 3.79, 3.78) | 0/3 (true d 3.78, 3.78, 3.78) |
| 06 | green stop sign | 0/3 (true d 5.04, 5.04, 5.05) | 0/3 (true d 5.05, 5.05, 5.05) |
| 07 | orange sports ball | 3/3 (true d 0.67, 0.68, 0.64) | 3/3 (true d 0.59, 0.63, 0.64) |
| 08 | blue chair | 0/3 (true d 0.87, 0.86, 0.99) | 3/3 (true d 0.65, 0.69, 0.71) |
| 09 | red stop sign | 0/3 (true d 1.27, 1.27, 1.27) | 0/3 (true d 1.27, 1.26, 1.28) |
| 10 | blue chair | 3/3 (true d None, None, None) | 3/3 (true d None, None, None) |
| | **all** | **9/30** (30 %) | **16/30** (53 %) |

| Class | baseline (merged main) | final (b/overnight-all) |
|---|---|---|
| chair | strict 0/12; SUCCESS 12 (true d mean/max 0.89/0.99, 12 > 0.80 m); stop_verification 0; contact 0 | strict 7/12; SUCCESS 9 (true d mean/max 0.76/1.04, 2 > 0.80 m); stop_verification 3; contact 3 |
| sports ball | strict 6/6; SUCCESS 6 (true d mean/max 0.66/0.68, 0 > 0.80 m); stop_verification 0; contact 2 | strict 6/6; SUCCESS 6 (true d mean/max 0.64/0.69, 0 > 0.80 m); stop_verification 0; contact 3 |
| stop sign | strict 0/9; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 | strict 0/9; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 |

**Strict S3: 9/30 (30 %) → 16/30 (53 %).** All of the gain is chairs (0/12 → 7/12): the baseline's 12 chair
"successes" all stopped at a true 0.83–0.99 m. Scenario 4 (red chair approached from the side) now fails
`stop_verification` 3/3 (overshoot to ~0.6 m, frame-filling chair), scenario 1 is 1/3; balls 6/6 on both sides;
stop signs 0/9 on both (never detected).

## Default vs hard scene (stretch, `assist/hard-scene`, not merged)

Hard scene (`main.py --scene hard`, `docs/hard_scene.md`): a second green chair next to the ball, two 1.2 m walls
hiding the yellow and green signs from the spawn, an orange box by the ball and a red box by the red chair, light at
55 %. Run `20261004-0247_hard_scene` (6 typed gotos, fresh launch each, clips `~/Videos/e2e/20261004-0247_hard_scene/`), compared with the closest default-
scene trials of the definitive final run:

| Target | Default scene (final) | Hard scene (S6) | What the hard scene shows |
|---|---|---|---|
| green chair | ✅ S3_03, true d 0.69 m | ❌ "go to the green chair": **timeout**, touched both chairs (true 0.94 m to #2) · ✅ "…next to the orange ball": 0.78 m to #2 (parsed as a plain green-chair goto; right chair by luck) | two identical targets: navigation switches between them; the action schema can't express "the one next to X" |
| red chair | ❌ S3_01 1.04 m · ✅ S4 multi-goal 0.69 m | ❌ `SUCCESS` but true **0.88 m** (est 0.52) | red box distractor next to the chair: the range estimate is off by +0.36 m |
| orange ball | ✅ S3_02 0.69 m, S3_07 0.59 m | ✅ 0.63 m (brushed the red sign pole on the way) | orange box distractor: no effect on detection; no obstacle avoidance |
| yellow stop sign | ❌ S3_05 not found | ❌ not found (expected: occluded) | signs aren't detected at all (see stop-sign item) |
| red stop sign | ❌ S3_09 not found | ❌ not found | dim light isn't the cause: the sign model is |
| **strict success** | — | **3/6** (incl. the expected occluded-sign failure) | |

## S1 — Task 2 skills (unchanged code: expect same)

| Scenario | Baseline | Final | Verdict | Clips (baseline / final) |
|---|---|---|---|---|
| closed | max abs error 1.9° | max abs error 2.0° | same | `20261004-0101_baseline/S1_closed.mp4` / `20261004-0221_final/S1_closed.mp4` |
| open | mean abs error 79.6° | mean abs error 79.6° | same | `20261004-0101_baseline/S1_open.mp4` / `20261004-0221_final/S1_open.mp4` |
| move | 2.24 m | 2.28 m | same | `20261004-0101_baseline/S1_move.mp4` / `20261004-0221_final/S1_move.mp4` |

## S2 — Task 3 (Video_Task3 script a–g typed into main.py)

| | Baseline | Final |
|---|---|---|
| pass | True | True |
| [CMD] lines as expected | 7 | 7 |
| turn errors (°) | [2.0, 1.5, -1.6] | [1.8, 1.3, -1.6] |
| contacts / fall | 0 / False | 0 / False |
| max tilt (°) | 7.4 | 7.0 |
| clip | `20261004-0101_baseline/S2_video_task3.mp4` | `20261004-0221_final/S2_video_task3.mp4` |

Final adds the talk-back lines (prompt v5), e.g. `Robot: Done: net turn 88° left.`; every handout line is unchanged.

## S3 — Task 4 (C's 10 scenarios, typed)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (10: correct `target_not_found`).

| # | Target | Baseline | P2a (main.py --scenario) | P2b v2 (per-class stop) | Final | Verdict | Clips (baseline / final) |
|---|---|---|---|---|---|---|---|
| 01 | red chair | ❌ SUCCESS, true d 0.85, 15.4 s | ❌ SUCCESS, true d 0.84, 13.2 s | ✅ SUCCESS, true d 0.74, 54.0 s | ❌ SUCCESS, true d 1.04, 71.8 s, contact | same | `20261004-0101_baseline/S3_01.mp4` / `20261004-0221_final/S3_01.mp4` |
| 02 | orange sports ball | ✅ SUCCESS, true d 0.66, 28.1 s | ✅ SUCCESS, true d 0.68, 34.7 s, contact | ✅ SUCCESS, true d 0.61, 28.3 s | ✅ SUCCESS, true d 0.69, 40.9 s, contact | same | `20261004-0101_baseline/S3_02.mp4` / `20261004-0221_final/S3_02.mp4` |
| 03 | green chair | ❌ SUCCESS, true d 0.94, 13.7 s | ❌ SUCCESS, true d 0.96, 14.1 s | ✅ SUCCESS, true d 0.68, 16.0 s | ✅ SUCCESS, true d 0.69, 15.4 s | **better** | `20261004-0101_baseline/S3_03.mp4` / `20261004-0221_final/S3_03.mp4` |
| 04 | red chair | ❌ SUCCESS, true d 0.84, 19.8 s | ❌ SUCCESS, true d 0.88, 19.8 s | ❌ FAIL stop_verification, true d 0.59, 25.2 s | ❌ FAIL stop_verification, true d 0.57, 25.6 s | **worse** | `20261004-0101_baseline/S3_04.mp4` / `20261004-0221_final/S3_04.mp4` |
| 05 | yellow stop sign | ❌ FAIL target_not_found, true d 3.78, 10.8 s | ❌ FAIL target_not_found, true d 3.78, 11.0 s | ❌ FAIL target_not_found, true d 3.78, 10.9 s | ❌ FAIL target_not_found, true d 3.78, 10.8 s | same | `20261004-0101_baseline/S3_05.mp4` / `20261004-0221_final/S3_05.mp4` |
| 06 | green stop sign | ❌ FAIL target_not_found, true d 5.04, 10.9 s | ❌ FAIL target_not_found, true d 5.03, 11.4 s | ❌ FAIL target_not_found, true d 5.04, 10.8 s | ❌ FAIL target_not_found, true d 5.05, 10.9 s | same | `20261004-0101_baseline/S3_06.mp4` / `20261004-0221_final/S3_06.mp4` |
| 07 | orange sports ball | ✅ SUCCESS, true d 0.67, 16.2 s | ✅ SUCCESS, true d 0.69, 16.5 s | ✅ SUCCESS, true d 0.6, 20.6 s | ✅ SUCCESS, true d 0.59, 20.8 s | same | `20261004-0101_baseline/S3_07.mp4` / `20261004-0221_final/S3_07.mp4` |
| 08 | blue chair | ❌ SUCCESS, true d 0.87, 18.6 s | ❌ SUCCESS, true d 0.89, 14.4 s | ✅ SUCCESS, true d 0.7, 21.6 s | ✅ SUCCESS, true d 0.65, 16.2 s | **better** | `20261004-0101_baseline/S3_08.mp4` / `20261004-0221_final/S3_08.mp4` |
| 09 | red stop sign | ❌ FAIL target_not_found, true d 1.27, 11.0 s | ❌ FAIL target_not_found, true d 1.27, 10.8 s | ❌ FAIL target_not_found, true d 1.28, 10.8 s | ❌ FAIL target_not_found, true d 1.27, 10.8 s | same | `20261004-0101_baseline/S3_09.mp4` / `20261004-0221_final/S3_09.mp4` |
| 10 | blue chair | ✅ FAIL target_not_found, true d None, 11.1 s | ✅ FAIL target_not_found, true d None, 11.0 s | ✅ FAIL target_not_found, true d None, 10.9 s | ✅ FAIL target_not_found, true d None, 10.9 s | same | `20261004-0101_baseline/S3_10.mp4` / `20261004-0221_final/S3_10.mp4` |
| | **strict success** | **3/10** | **3/10** | **6/10** | **5/10** | | |

## S4 — Bonus

| Look question | Baseline answer | Final answer |
|---|---|---|
| what can you see? (after turn around) | I see a checkered floor with blue and dark blue squares, a large red square sign on a gray pole in front, a green sign to the left, a yellow sign to the right,  | I see a checkered blue-and-dark-blue floor with several colored objects: a large red square sign on a gray pole in the center, a green rectangular sign to the l |
| is there a chair in front of you? (after turn right 45) | Yes, there is a green chair in front of you, positioned toward the center-right of the view. | Yes, there is a green chair in front of you, positioned on the checkered floor. |
| what colour is the ball ahead? (after turn left 90) | There is no ball visible ahead in the image. The objects present are a red chair and a green square on a stick. | There is no ball visible ahead in the image. The objects present are a red chair and a green square on a pole. |

Clips: `20261004-0101_baseline/S4_look.mp4` / `20261004-0221_final/S4_look.mp4`. Correctness checked by hand against the saved frames (see MORNING_BRIEF.md).

| Multi-goal (red chair, then orange ball) | Baseline | Final |
|---|---|---|
| `[MULTI]` | `[MULTI] status=SUCCESS reached=2/2 t=45.6 s` | `[MULTI] status=SUCCESS reached=2/2 t=53.9 s` |
| true d at stops | [0.88, 0.67] | [0.69, 0.58] |
| strict C2 (all ≤ 0.80 m) | False | True |
| clip | `20261004-0101_baseline/S4_multigoal.mp4` | `20261004-0221_final/S4_multigoal.mp4` |

## S5 — B upgrades (final only; new features)

| Scenario | Checks | Pass | Clip |
|---|---|---|---|
| estop | estop_line ✅, no_llm_for_stop ✅, [ESTOP] software latency 0.0 ms | ✅ | `20261004-0221_final/S5_estop.mp4` |
| non_english | rejected_non_english ✅, suggestion ✅, redirect_turned ✅ | ✅ | `20261004-0221_final/S5_non_english.mp4` |
| out_of_range | rejected_out_of_range ✅, suggestion ✅, why_answer ✅ | ✅ | `20261004-0221_final/S5_out_of_range.mp4` |
| return_home | plan ✅, home_within_0.3m ✅, status_answer ✅ | ✅ | `20261004-0221_final/S5_return_home.mp4` |
| square | plan ✅, four_sides ✅, closed_back_within_0.5m ✅, summary ✅ | ✅ | `20261004-0221_final/S5_square.mp4` |
| status | answer_mentions_turn ✅ | ✅ | `20261004-0221_final/S5_status.mp4` |
| until_see | until_line ✅, found_ball ✅, mission_success ✅, summary ✅ | ✅ | `20261004-0221_final/S5_until_see.mp4` |
