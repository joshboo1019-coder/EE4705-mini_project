# Reactive avoidance during the approach (iter/avoid)

Change contributed by Student B (assist), pending review by Student C.

Branch `iter/avoid`, from `rc` (`ee1ce2b`) plus `origin/iter/stopsign-plate` (`4ede3ed`, the colour-plate stop-sign
fallback, `docs/iter_stopsign_plate.md`). Only `perception/navigation.py` (new helpers plus three call sites) and
`tests/test_avoid.py` change. The scene is unchanged.

## Problem

- **S3_02 (orange ball):** the red stop sign stands on the straight line from the robot to the ball. On `final-r2` the
  robot touched the sign in 5 of 5 runs.
- **S3_06 (green stop sign):** the green chair stands between the robot and the green sign.
  - From the start pose the plate is hidden behind, or merged with, the chair's edge-on backrest, so the in-place
    scan sees nothing.
  - When the plate is seen, the straight-line approach walks into the chair.

## Method

All of this uses live detections and the robot's own pose. Ground truth is used only in the `[RANGE]`/`[FOUND]` log
distance and in the e2e evaluation. `tests/test_no_ground_truth.py` passes.

1. **Obstacles** (`_obstacle_estimates`), computed each approach step before the forward step:
   - The sources are every live YOLO detection of a known class (chair, sports ball, stop sign) that is not the
     commanded target, plus the colour-plate detector (`perception.detect_plate`) for red, yellow and green signs.
     The target's own colour is skipped when the goal is a sign.
   - Each obstacle is ranged with the target's bbox models (`_estimated_target_position`: height-aware ray, size
     model, or the sign plate model).
   - A detection within 0.45 m of the target estimate is treated as the target.
   - Each obstacle's last live estimate is kept for 6 s and moved with the robot's pose. Up close, YOLO drops a
     frame-filling chair; the memory keeps it in the check.
2. **Decision** (`_avoid_decision`, pure function): the rule triggers when all of these hold:
   - a non-target obstacle is estimated < 1.0 m away;
   - any part of it is within ±25° of the heading. Each class has a half-width prior: chair 0.25 m, ball 0.11 m,
     sign pole 0.05 m (the plate is at 0.70–1.00 m, above the body);
   - it is nearer than the target by at least 0.20 m.

   The robot then steps sideways away from the obstacle, relative to the target line. The side is fixed per obstacle
   label, so the robot does not zig-zag.
3. **Action** (`_avoid_obstacle_ahead`):
   - log `[AVOID] obj=<label> d_est=<m> side=L|R`;
   - strafe 0.3 m/s for 0.5 s (about 0.15 m);
   - re-run the loop: detect, steer, re-check.

   This repeats until the obstacle leaves the cone, with at most 12 steps per goal (about 1.8 m sideways).
4. **One occlusion side-step for sign goals** (`_occlusion_sidestep`): after a full in-place scan finds no "stop sign"
   target, the robot steps 0.8 m left once and scans again. A thin sign plate can hide behind a nearer object.
   `target_not_found` is still reported after the second scan. Other classes are unchanged, so S3_10 (absent blue
   chair) behaves as before.
5. **Short steps at a top-cut sign plate** (`_sign_creep_distance`): once the plate is cut by the top edge of the
   frame, the forward step is 0.07 m instead of 0.15 m. The near-strip stop rule then fires before the plate leaves
   the frame.

   In dev run 2 (S3_05), the plate was lost at a true 0.77 m. The growing re-acquire strafes that followed touched
   the target sign (6 contact samples).

Handout lines (`[SEARCH]`/`[DETECT]`/`[FOUND]`/`[MISSION]`, `[CMD]`/`[EXEC]`/`[DONE]`) are unchanged. The new lines
are `[AVOID] …` and `[SEARCH] full scan without the target, side-stepping left 0.8 m to look past occluders`. Obstacle
plate checks also print the existing `[PLATE] …` line.

Unit tests (`tests/test_avoid.py`) cover:
- the cone, range and target-margin rule;
- the nearest-obstacle choice and the sticky side;
- partial cone overlap;
- the exact `[AVOID]` line;
- the step budget;
- the obstacle memory;
- the one-time side-step;
- the creep rule.

## Dev runs (not gated)

| run | code | S3_02 | S3_05 | S3_06 | S3_09 |
|---|---|---|---|---|---|
| dev1 | `[AVOID]` only | ✅ 0.74 m, other contacts 0 (6 `[AVOID]`) | – | ❌ target_not_found (no plate in any view) | – |
| dev2 | + occlusion side-step | ✅ 0.71 m, other 0 (5 `[AVOID]`) | ✅ 0.75 m but 6 **target** contact samples | ✅ 0.71 m, 14 contact samples with the green chair | ✅ 0.71 m |
| dev3 | + whole-object cone, memory, creep | not run: cancelled to fit the gate in the time box. The gate is the first sim test of this code. | | | |

## Gate (e2e S3 full, n = 3, `--s3-path main`, no video)

- **Code:** `0b91b6f`, which is `add0e28` plus `origin/rc` at `fa17c08`. `fa17c08` contains fix/hygiene, not
  iter/chair-safety, which was not in rc yet.
- **Runs:** `p2b_gate_r1` to `r3`: `eval/e2e/results/20261004-1725_p2b_gate_r1`, `eval/e2e/results/20261004-1732_p2b_gate_r2`, `eval/e2e/results/20261004-1745_p2b_gate_r3`.
- **Strict success:** SUCCESS, true d ≤ 0.80 m and C1 (S3_10: the correct `target_not_found`). True distance and
  contacts come from the trace and are used for evaluation only.
- **False `[FOUND]`:** a `[FOUND]` for the wrong object or at a true d > 0.80 m.

| # | target | strict | true d | target-contact runs | other-contact runs (objects) | false [FOUND] | [AVOID] lines per run | min |
|---|---|---|---|---|---|---|---|---|
| 01 | red chair | 3/3 | 0.61, 0.57, 0.63 | 0 | 0  | 0 | 2, 2, 0 | ≥1 ✅ |
| 02 | orange sports ball | 3/3 | 0.58, 0.64, 0.63 | 0 | 1 (red_stop sign) | 0 | 12, 10, 12 | ≥2 ❌ |
| 03 | green chair | 2/3 | 0.56, 0.69, 0.7 | 1 | 0 (green_chair) | 0 | 1, 2, 1 | ≥2 ❌ |
| 04 | red chair | 3/3 | 0.56, 0.67, 0.66 | 1 | 0 (red_chair) | 0 | 0, 1, 1 | ≥1 ❌ |
| 05 | yellow stop sign | 3/3 | 0.6, 0.72, 0.73 | 0 | 0  | 0 | 0, 0, 0 | ≥2 ✅ |
| 06 | green stop sign | 1/3 | 0.8, 0.86, 0.83 | 0 | 1 (green_chair) | 2 | 3, 3, 12 | ≥2 ❌ |
| 07 | orange sports ball | 3/3 | 0.65, 0.66, 0.62 | 0 | 0  | 0 | 0, 4, 0 | ≥2 ✅ |
| 08 | blue chair | 3/3 | 0.7, 0.67, 0.64 | 0 | 0  | 0 | 0, 0, 0 | ≥2 ✅ |
| 09 | red stop sign | 2/3 | 0.64, 0.72, 0.55 | 1 | 0 (red_stop sign) | 0 | 0, 0, 0 | ≥2 ❌ |
| 10 | blue chair | 3/3 | None, None, None | 0 | 0  | 0 | 0, 0, 0 | ≥2 ✅ |
| | **all** | **26/30** | | | | | | **FAIL** |

### Gate criteria

| criterion | result | met |
|---|---|---|
| S3_02 other-object contact runs 0/3 | 1/3 | ❌ |
| S3_05 ≥ 2/3 strict | 3/3 | ✅ |
| S3_06 ≥ 2/3 strict | 1/3 | ❌ |
| S3_09 ≥ 2/3 strict | 2/3 | ✅ |
| zero false [FOUND] | 2 (06) | ❌ |
| no target contact in any run | S3_03 in 1 run(s), S3_04 in 1 run(s), S3_09 in 1 run(s) | ❌ |
| 01 ≥ 1/3, 04 ≥ 1/3 | 01 3/3, 04 3/3 | ✅ |
| 02, 03, 07, 08, 10 ≥ 2/3 | 02 3/3, 03 2/3, 07 3/3, 08 3/3, 10 3/3 | ✅ |

### What went wrong

- **S3_02, r1: contact with the red sign (15 samples).** The robot side-stepped right past the sign. A phantom
  `unknown sports ball` then appeared at about 0.9 m (YOLO on the ball's floor reflection, below the real ball) and
  became an obstacle. The 6 s memory kept it for 6 more `[AVOID] … side=L` steps, which pushed the robot back toward
  the sign; the rear-left thigh touched the pole. In r2 there was no contact.
- **S3_03, r1: target contact and failure.** The red chair, cut by the left frame edge, was ranged at 0.86 m (true
  about 2.5 m) and caused one `[AVOID]`. The robot later lost the green chair, and the old re-acquire strafes walked
  into it (274 samples). That strafe behaviour is the subject of iter/chair-safety, which was not in rc yet.
- **S3_04, r1: target contact (62 samples), still a strict success.** This is the known red-chair close-range
  contact; no `[AVOID]` was involved.
- **S3_06, r2: false `[FOUND]` at a true 0.86 m.**
  - The short steps (0.07 m) at a top-cut plate let the plate's visible strip drop to 33 px at a true 0.87 m.
  - The plate branch's near-strip rule (≤ 40 px → 0.70 m) then overrode the width model, which said 0.86 m and was
    right, so the robot stopped about 0.15 m early.
  - Without the short steps, the robot jumped through this band.
- **Run r3:**
  - S3_06 had a second false `[FOUND]`, at a true 0.83 m (same near-strip/creep cause), and 30 contact samples with
    the green chair after 12 `[AVOID]` steps; the step budget ran out.
  - S3_09 timed out at a true 0.55 m with 19 target-contact samples: the plate was lost at close range.
- **Reading the table:** the "(objects)" list in the gate table names every object touched, including the target.
  The count before it is runs with contact with a non-target object.
- **Positives:**
  - S3_06's search failure is fixed: the one side-step after a failed scan found the plate (r2), and S3_06 passed
    without chair contact in r1 and r2.
  - S3_02 kept its success with the sign avoided in r2.
  - The stop-sign scenarios had no target contact.

Next steps (not done, time box):
1. Ignore obstacle detections whose colour is `unknown`, which are floor reflections and phantoms.
2. Ignore obstacle detections cut by the left or right frame edge, whose range is unreliable.
3. Remember only obstacles that actually triggered `[AVOID]`.
4. Apply the sign near-strip rule only when the width model is unavailable, or take the larger of the two.
5. Re-gate after iter/chair-safety is in rc.

## Verdict

**FAIL** (S3 strict 26/30 over n = 3; `final-r2` reference 28/50 = 16.8 per 30). Failed: S3_02 other-object contact runs 0/3; S3_06 ≥ 2/3 strict; zero false [FOUND]; no target contact in any run. **Don't merge as is**; see the next steps above.
