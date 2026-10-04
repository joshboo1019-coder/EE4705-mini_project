<!-- Contributed by Student B (assist), pending review by Student C. -->
# Task 4 — no simulator ground truth in the range estimate (`assist/no-gt-height`)

**Problem.** `navigation._camera_height_above_ground` called `_target_center_world_height`, which found the
target's body in the compiled MuJoCo model by its material colour and read its **live world height from the
simulator** (`data.xpos[body_id][2]`). That height feeds `_estimated_target_position` → the estimated range → the
stop decision and the C2 check. It is ground truth in the control path; ground truth may only be used for the
`[RANGE] … ground_truth=` / `[FOUND] … d=` logs (docs/STUDENT_README.md, "What NOT to do").

**Change** (`perception/navigation.py`, minimal; header line in the file):

- The **camera** height still comes from the robot's own measured trunk height (`get_trunk_height()`), i.e.
  proprioception, in the same category as `get_robot_pose()`.
- The **target centre** height is no longer read from the simulator:
  - floor targets: a nominal height per *class* — chair 0.44 m, sports ball 0.11 m, stop sign 0.50 m (Student C's
    constants; the old table was keyed by colour+class and gave `blue_chair` the stairs height 0.84 m, which is wrong
    for the floor-standing blue chairs of scenarios 3, 8 and 10);
  - elevated targets (chairs and balls): estimated from the live bbox — range by known size (f · H / bbox height),
    then the bbox centre's height from the ray through it, `z = camera_z − range · tan(ray_down)`. Used only when it
    is ≥ 0.20 m above the class's nominal height; a bbox that is tiny or cut by the frame edge falls back to the
    nominal height; stop signs always use the nominal height.
- `_find_target_body_id` / `_geometry_matches_class` (the simulator lookup) are removed — they had no other users.
- `tools/visual_test_blue_chair_stairs.py` passes the bbox to the same function for its own range log.
- `tests/test_navigation_reacquire.py`: the test that asserted the `data.xpos` behaviour is replaced by 5 tests
  (navigation never touches `skills._model` / `_data`; floor → nominal; elevated chair recovered from a synthetic
  bbox at 1.5/2.5/3.5 m; cut/tiny bbox → nominal; signs → nominal). Suite: 260 passed, 1 xfailed.

Ground truth is now read only by `_ground_truth_distance` (the `[RANGE] ground_truth=` and `[FOUND] d=` logs).

## Before / after (real sim, typed through `main.py --scenario`, fresh launch each, recorded)

Before = `b/overnight-all` after merging main `bdee10a` (simulator height); after = this branch. S3 n = 1 per side,
S7 n = 2 per side. Neither version meets strict C2 on the stairs; for floor targets the two are equivalent.

| | Before (simulator height) | After (no ground truth) |
|---|---|---|
| S3 strict success (true d ≤ 0.80 m and C1) | **6/10** (`20261004-1206_morning_merge`) | **6/10** (`20261004-1216_no_gt_height`) |
| S3 per scenario | ✅ 02 03 04 07 08 10 · ❌ 01 (stop_verification) 05 06 09 | ✅ 01 02 03 07 08 10 · ❌ 04 (stop_verification) 05 06 09 |
| S3 true d at SUCCESS stops | 0.59–0.71 m | 0.59–0.76 m |
| Floor targets | simulator height = nominal (chair body at z 0 + 0.44, ball 0.11, sign 0 + 0.50) | nominal; the elevation trigger never fired on 94 floor-chair detections (estimated centre height median 0.42 m vs nominal 0.44) |
| S7 blue chair on the stairs (n = 2 each) | ❌ `target_not_found`, ❌ `timeout` — estimate accurate (true − est ≈ +0.1 m), robot got as close as 0.45 m but lost the chair while re-acquiring | ❌ `SUCCESS` at true **0.95 m** (C2 ✗), ❌ `stop_verification` at 0.91 m — estimate ~0.40 m short |
| S7 runs | `20261004-1213_stairs_before_gt`, `…1225_stairs_before_gt_rep2` | `20261004-1216_no_gt_height`, `…1227_stairs_no_gt_rep2` |

Scenarios 1 and 4 (the red chair) alternate between `SUCCESS` and `stop_verification` from run to run on both
sides (last night: 1/3 and 0/3 with the simulator height), so the 01/04 swap is run-to-run variation, not this
change: for floor targets the two versions compute the same height.

## The stairs case (S7): what the bbox estimate can and can't do

S7 runs Student C's own sequence (`tools/visual_test_blue_chair_stairs.py`: walk to the stairs, detect, climb,
then `goto_object` for the final approach), recorded; ground truth from its `[RANGE]` logs.

- **Before** (simulator height): the range estimate is accurate on the elevated chair (true − est ≈ +0.1 m), but
  the per-class chair stop (0.56 m, calibrated on *floor* chairs whose estimate reads 0.17 m short) asks the robot
  to get closer than it can hold the chair in view on the stairs: it paused at est ≈ 0.75 m / true ≈ 0.84 m, lost the
  chair, re-acquire strafes took it as close as 0.45 m, and both runs failed (`target_not_found`, `timeout`).
- **After** (no ground truth): the elevation estimate works (bbox centre 0.80 m vs the true 0.84 m on the first
  frames), but ranging by size reads ~20 % short on this view — the chair's YOLO box behaves like a 1.1 m tall
  object here, against 0.93 m (median of 408 floor-chair detections tonight) and the 0.88 m nominal. So the range is
  ~0.40 m short and the robot stops at a true 0.91–0.95 m: one `SUCCESS` (C2 not met), one `stop_verification`.
- Calibrating the size constant to the floor median (0.93 m) would only move the error to ~0.40 m; fitting it to
  the single elevated chair would be tuning on the test case. **Limitation, documented:** without ground truth an
  elevated target's range is only as good as its size prior. Options for C: a second detection pass from a closer
  pose before the final step, or a stairs-specific stop distance justified by more than one object.

Ground truth for this table comes from the e2e logs only; nothing in the control path reads it.
