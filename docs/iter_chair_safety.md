# iter/chair-safety — target safety during re-acquire + red-chair "bed" analysis

Change contributed by Student B (assist), pending review by Student C
(owner of perception/navigation.py). Branch `iter/chair-safety` from `rc`.

## 1. Back-off rule (perception/navigation.py, core/config.py)

F5 contact evidence on tag `final`: the red chair was touched in 3/10 S3_01/S3_04
runs, during the re-acquire strafe (0.4 m/s sideways, 1.1 s+ per sweep) after the
chair was lost close-up (frame-filling chair labelled "bed" or dropped by YOLO).

Rule (new): when the target is lost and the robot's **own last range estimate**
(`[RANGE] estimated_planar`, never ground truth) is below
`stop distance + CLOSE_REACQUIRE_MARGIN_M` (0.56 + 0.15 = 0.71 m for chairs):

* no strafe: `_close_range_reacquire` backs off `CLOSE_REACQUIRE_BACKOFF_M`
  (0.25 m, clamped to >= 0.25) straight back with the move skill, re-faces the
  estimated target point, then rotates **in place** (0, +s, -s with
  s = 20 deg x attempt, capped at 60 deg) and stops at the first heading with a
  live detection (heading restored if none);
* the stuck-recovery path (forward progress blocked) skips its own 0.15 m
  back-up + strafe and runs the same back-off + rotate;
* no forward step on a tracker-only target (detector lost it) inside that range.

Far from the target (estimate >= stop + 0.15 m) the original strafe sweep is
unchanged. Handout log lines ([SEARCH]/[DETECT]/[FOUND]/[MISSION], [CMD]/[EXEC]/[DONE])
are byte-identical; the change only adds `[REACQUIRE] ...` lines.
Tests: `tests/test_chair_safety.py` (6 tests); full pytest 291 passed, 1 xfailed;
`tests/test_no_ground_truth.py` green.

## 2. Red chair labelled "bed": offline analysis (no control change from GT)

Data: `results.jsonl` (`lines` = [epoch, text]; `[RANGE] estimated_planar=E
ground_truth=G phase=...`, `[DETECT]` lines of the same iteration; `eval.true_d`
from the trace) of every S3_01/S3_04 run in `eval/e2e/results/*`,
`docs/report_assets/final/e2e_runs/*`, `~/Videos/e2e/{final_tag_raw,iter1_raw,iter2_raw}`
(deduplicated by run dir): **n = 51 red-chair runs** (23-25 on current code).
Ground truth used here for offline analysis only.

Label vs true distance (approach iterations, binned):

| true d (m) | chair seen (conf >= 0.25) | "bed" seen |
|---|---|---|
| >= 0.80 | 83/94 | 1/94 |
| 0.75-0.80 | 16/24 | 1/24 |
| 0.70-0.75 | 5/27 | 10/27 |
| 0.65-0.70 | 3/34 | 8/34 |
| < 0.65 | 0/30 | 0/30 (tracker only) |

* **Label flip chair -> "bed" at true d ~ 0.70-0.75 m** ("bed" in 17/51 runs, at
  0.68-0.74 m); below ~0.65 m YOLO reports neither, only the tracker holds it.
  Per run (n = 44), last chair detection before the loss: median true 0.90 m
  (0.76-1.15); first no-chair iteration below 1 m: median 0.66 m (0.56-0.88).
* **Range estimate error (est - true), true d 0.5-1.0 m: mean -0.12 m, median
  -0.12 m, range -0.17 .. -0.06 m (n = 170 pairs)**; flat across bins, same on
  current code (n = 87). The estimate reads ~0.12 m short.
* Current chair stop `APPROACH_STOP_M_BY_CLASS["chair"] = 0.56` -> final true d
  on current code (n = 23): min 0.57, median 0.64, max 0.91 (0.77 / 0.91 are
  re-approaches after a "bed" loss). Harness strict success: SUCCESS and
  true d <= 0.80 and C1 (no class-specific minimum).

Margin decision: stopping at true ~ 0.70 needs a chair stop of ~0.66 (replay of
each run's first approach pass on current code: median true 0.70, max 0.80,
**2/25 runs > 0.78**); a plain +0.06 shift of every logged final distance gives
max 0.97 (2 runs > 0.78). The criterion "every logged chair run still at true
d <= 0.78" is therefore **not met -> chair stop margin kept at 0.56** (no
config change). Candidate for Student C, not adopted/validated here: 0.62
(replay median 0.64, max 0.74, 0/25 > 0.78) — but it still stops inside the
0.68-0.74 m "bed" band, so it would not remove the mislabel. No label
remapping: "bed" is never accepted as chair.

## 3. Gate (sc01 + sc04 n=3, then sc03 + sc08 n=2)

Code `9412469` (rc + back-off rule; chair stop 0.56 unchanged), `--s3-path main --no-video`,
one run per sim-lock acquisition. Runs: `eval/e2e/results/20261004-1703_chair_s14_r1`,
`-1706_chair_s14_r2`, `-1712_chair_s14_r3`, `-1715_chair_s38_r1`, `-1724_chair_s38_r2`
(summary.md + results.jsonl committed; traces not). Contacts = trace contact samples
target / other objects / terrain.

| Scenario | strict k/n | true d at stop | target contacts | final-r2 ref |
|---|---|---|---|---|
| S3_01 red chair | **3/3** | 0.71, 0.64, 0.79 | **0/3** | 2/5 |
| S3_04 red chair | **2/3** | 0.61, 0.64, 0.66 (FAIL stop_verification) | **0/3** | 2/5 |
| **sc01 + sc04** | **5/6** (gate >= 3/6) | | **0/6** (gate 0) | 4/10, contacts 3/10 |
| S3_03 green chair | 1/2 | 0.71, 0.71 (r2 FAIL stop_verification) | 0/2 | 5/5 |
| S3_08 blue chair | 1/2 | 2.47 (r1 FAIL target_not_found), 0.66 | 0/2 | 5/5 |

The close-range path fired twice (S3_01 r1 at est 0.61 m, S3_01 r3 at est
0.58 m): back-off 0.25 m + in-place rotation, re-acquired, SUCCESS, no contact.
No run strafed next to a target; 0 contacts of any kind in 10 runs.

Stage-2 failures, inspected:
* S3_08 r1 `target_not_found`: no blue detection in the whole 360 deg search
  (0 `[DETECT] ... color=blue` lines), so the target was never acquired and the
  new code path (only reachable after acquisition, finite range estimate) never
  ran — detection-side, same code as rc.
* S3_03 r2 `stop_verification` at true 0.71 m: live detection at est 0.60 m,
  normal approach step, tracker recovery at est 0.45 m, stop check + [VERIFY]
  retry found no green chair (the known close-range C1 loss); no `[REACQUIRE]`,
  no blocked tracker-only step.


## Verdict

**FAIL** (strict gate). Stage 1 PASS: sc01 + sc04 5/6 strict, 0/6 target
contacts (final-r2: 4/10, 3/10 contacts on the red chair). Stage 2 not "all
success": sc03 1/2, sc08 1/2; both failures are on paths the change does not
touch (blue chair never detected; green-chair close-range C1 loss), but n=2
cannot show that statistically, so this is reported as a FAIL, not waived.
Chair stop margin unchanged (0.56). Recommended next step for Student C: re-run
sc03/sc08 at n=5 to separate the change from the known detection/C1 variance.
