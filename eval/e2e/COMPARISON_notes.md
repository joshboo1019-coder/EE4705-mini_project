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
