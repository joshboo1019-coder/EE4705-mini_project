# Task 4 — colour grounding fix and detection diagnostics

Branch `fix/task4-color-grounding` (from `origin/main` at `9dbd91e`), 2026-10-03. Written by Student B
(assist), for Student C to review. The only runtime change is `RealPerception._grounded_color` in
`perception/perception_real.py`. The `Detection` output, the `detect(frame, conf_threshold=None)` signature,
the colour names and the `[DETECT]` format are unchanged, and `navigation.py`, the scene and the Task 4 config
are untouched.

## Where the bug came from

The real-sim visual-QA check (`eval/results/vlm/20261002-232010-*.png`, on `bonus_b`) logged
`chair color=blue conf=0.50` for the **red** chair. That run used `bonus_b`'s copy of `perception_real.py`,
which predates C's `9da795e` "improved color classification" (2026-10-02 22:19) on main. On that exact frame and
bbox:

| `_grounded_color` version | red chair in the field frame |
|---|---|
| `bonus_b` (pre-`9da795e`, median hue of the inner half) | **blue** |
| `main` (`9da795e`, per-range pixel counts in the inner half) | red |
| this branch | red |

So **main already fixed the reported case.** None of C's newest branches (`task_4_021026`,
`task4_1520hrs_0210`, `task_4_improve`) changes `perception_real.py` relative to main. This fix builds on
main's version and removes the remaining error sources measured below.

## Test set (offline only)

`tools/task4_color_testset.py` loads the real composed scene through `RealSkills`, so the robot, lighting,
skybox and the 640×480 `dog_front_camera` (fovy 80°) are exactly the runtime ones. It then stops the sim thread
and teleports the trunk (standing pose, trunk 0.32 m above the ray-cast ground) to viewpoints around each graded
object, facing it (±12° yaw offset on some views). `MUJOCO_GL=egl`.

- **Tuning set:** 8 bearings × 4 distances (0.8, 1.4, 2.0, 2.5 m) per object, giving 210 frames (positions
  inside another object are skipped).
- **Held-out set:** bearings shifted by half a step, distances 1.1, 1.7 and 2.3 m, giving 156 frames. It was
  scored once with the final thresholds, with no retuning.
- YOLO runs with the current config (`yolo11n.pt`, conf 0.2, imgsz 736), and **every** detection is kept.
- **Labels come from MuJoCo segmentation renders**, which give each object's visible pixels (so occlusion is
  handled). A detection is labelled with the object of its own YOLO class that has ≥ 60% of its visible pixels
  inside the box. Failing that, it's the object with the most pixels in the box, if that object holds ≥ 70% of
  the object pixels there and ≥ 30% of its own visible pixels. Anything else is "unmatched".
- Ground-truth positions are used **only** here, for offline labelling.

```bash
MUJOCO_GL=egl python tools/task4_color_testset.py render --out DIR [--holdout]
python tools/task4_color_testset.py detect --out DIR [--model yolo11s.pt --tag yolo11s]
python tools/task4_color_testset.py score  --out DIR --field color_new --recompute
```

`docs/task4_color_grounding_crops.png` shows 4 crops per object with the old, main and new labels. Cases where
the versions disagree are chosen first, so it shows the new code's failures too.

## What the measurements showed

HSV of the actual object pixels from the segmentation masks (tuning set, 5th–95th percentile):

| | hue (°) | saturation | notes |
|---|---|---|---|
| red chair / red sign | 0 | 219–240 | |
| green chair / green sign | 126 / 132–142 | 206–213 | |
| blue chair | **226** | 219–222 | |
| orange ball | 32–**50** | 206–229 | specular highlights clip at V = 255 and drift towards yellow |
| yellow sign | 50 | 241 | |
| floor and sky | **210** | 128–171 | passes the old S ≥ 64 filter |
| beige terrain blocks | ~51 | ~70 | passes S ≥ 64 and reads as **yellow** |

The old inner-half crop let the blue floor and sky vote (bonus_b), and main's version still lets the beige
terrain and clipped highlights vote.

## The fix (`_grounded_color`)

1. **Background model from a ring** around the bbox (width 15% of the longer side, at least 4 px). A
   (hue ±10°, saturation ±32) colour counts as background if it covers ≥ 2% of the ring **and** is at least as
   dense in the ring as inside the box. That second test keeps an object's own colour when the object sticks
   out of its box, which happens with close chairs.
2. Drop pixels with **S < 160**, V < 32, or **V > 250** (clipped highlights). The objects render at S ≥ 206;
   the floor and sky are at 128–171 and the terrain at about 70.
3. Hues with no colour name (the 170–220° gap, i.e. floor reflections) don't vote.
4. **Dominant hue over the full bbox:** a circular 10° histogram (so red at 350–10° stays together), smoothed
   with its neighbours. Each pixel is weighted towards the box centre (Gaussian, σ = 0.5 × half-size; edge weight
   0.14), so a second object at the box edge votes less. The peak is refined by a circular mean and named with
   C's unchanged `_COLOR_HUE_RANGES`.
5. Fewer than max(12 px, 0.2% of the box) foreground pixels → **"unknown"**.

`_target_color_fraction` (the recovery tracker) is unchanged.

## Before / after: grounding accuracy on the same detections

Tuning set (350 labelled detections; 13 boxes hold two graded objects):

| Object | bonus_b (old) | main | **this branch** |
|---|---|---|---|
| green chair | 50/70 | 69/70 | **70/70** |
| red chair | 60/78 | 77/78 | **78/78** |
| blue chair | 67/69 | 67/69 | 65/69 |
| orange ball | 88/88 | 79/88 | **88/88** |
| red sign | 6/19 | 17/19 | **19/19** |
| yellow sign | 2/9 | 9/9 | 9/9 |
| green sign | 7/17 | 15/17 | **17/17** |
| **total** | 280/350 (80.0%) | 333/350 (95.1%) | **346/350 (98.9%)** |
| one object in the box | 271/337 | 321/337 | **335/337** |

Held-out set (286 labelled detections, not used for tuning):

| Object | bonus_b (old) | main | **this branch** |
|---|---|---|---|
| green chair | 42/58 | 56/58 | **57/58** |
| red chair | 52/71 | 67/71 | **70/71** |
| blue chair | 54/54 | 52/54 | 52/54 |
| orange ball | 68/68 | 68/68 | 68/68 |
| red sign | 4/21 | 13/21 | **21/21** |
| yellow sign | 0/4 | 4/4 | 4/4 |
| green sign | 5/10 | 10/10 | 10/10 |
| **total** | 225/286 (78.7%) | 270/286 (94.4%) | **282/286 (98.6%)** |

Confusion, tuning set (rows = true colour, columns = grounded colour):

| main | red | orange | yellow | green | blue | unknown |
|---|---|---|---|---|---|---|
| red | 94 | | 3 | | | |
| orange | | 79 | **9** | | | |
| yellow | | | 9 | | | |
| green | | | 2 | 84 | 1 | |
| blue | 2 | | | | 67 | |

| this branch | red | orange | yellow | green | blue | unknown |
|---|---|---|---|---|---|---|
| red | 97 | | | | | |
| orange | | 88 | | | | |
| yellow | | | 9 | | | |
| green | | | | 87 | | |
| blue | **4** | | | | 65 | |

**Background boxes.** 274 random boxes containing no graded-object pixels (floor, sky, terrain), sampled from
the tuning frames: this branch returns "unknown" for 273 (one "red"). Main returns "unknown" for 242, "yellow"
for 22, "blue" for 8 and "green"/"purple" for 1 each. Unmatched YOLO detections (no graded object): main
yellow 14 / unknown 6 / green 1; this branch unknown 15 / red 4 / green 1 / blue 1.

**What's still wrong.** All 4 tuning-set errors are the blue chair on the stairs read as red. The 4 held-out
errors are one each of blue → red, blue → green, green → yellow and red → green. In each, YOLO's *chair* box also covers the nearer red stop sign's face, which has more red pixels
than the far chair has blue. Main's inner-half crop gets these right more often (12/13 two-object boxes vs 11/13
here), because YOLO centres the box on the chair. A tighter centre weighting (σ = 0.35) gives 347/350 but
ignores the box edges almost entirely, so it was not used. A box deep inside a solid object, with the ring full
of the object's own colour, comes out "unknown", not a wrong colour (see the unit tests).

**Tests.** `tests/test_color_grounding.py` has 8 synthetic-crop tests:
- a thin red frame on a blue background → red;
- a thin green frame → green;
- a solid blue object on the navy floor → blue;
- the orange ball with a clipped highlight → orange;
- 4 stray red pixels → unknown;
- floor and sky alone → unknown;
- an object sticking out of its box keeps its colour;
- invalid boxes → unknown.

All 8 pass. Main's version fails the stray-pixels test (it says "red"). Full suite: 26 passed, 5 failed. The
same 5 fail on a clean `origin/main` worktree (18 passed there): `test_handoff::test_main_wires_mocks_by_default`
and 4 tests in `test_navigation_reacquire` (`remember_target_retains_last_twenty_png_bbox_frames`,
`steer_to_center_accepts_target_within_wider_tolerance`,
`obstructed_approach_backs_up_strafes_and_retries_scan`, `recenter_time_counts_toward_four_second_recovery`).
So none of them comes from this change.

## Detection misses (diagnostic only; defaults not changed)

Detection rate = frames where the object is visible (≥ 60% of its projected box in the image and ≥ 300 seen
pixels) in which a detection of the right YOLO class covers it. Conf 0.2, imgsz 736, CPU (Ryzen 9 7945HX,
`CUDA_VISIBLE_DEVICES=`). Both sets combined:

| Object | yolo11n (current) | yolo11s |
|---|---|---|
| green chair | 104/158 (66%) | 91/158 (58%) |
| red chair | 123/152 (81%) | 113/152 (74%) |
| blue chair | 87/102 (85%) | 93/102 (91%) |
| orange ball | 117/117 (100%) | 107/117 (91%) |
| red stop sign | 3/136 (2%) | 0/136 |
| yellow stop sign | 2/127 (2%) | 0/127 |
| green stop sign | 2/124 (2%) | 0/124 |
| CPU inference + grounding per frame, median | **22 ms** | 41–49 ms |

By distance (all chairs): yolo11n detects 36/48 below 1.2 m, 54/55 at 1.2–1.9 m and 224/309 at ≥ 1.9 m;
yolo11s 36/48, 51/55, 210/309. The ball is near 100% at every distance with yolo11n. yolo11s loses 9/24 balls
below 1.2 m.

- **yolo11s is not better on this scene**: it's slightly better on the blue chair, worse on the other chairs and
  the ball, and about 2× slower. These numbers don't support switching to it.
- **Stop signs are almost never detected as "stop sign"** (7/387 with yolo11n). The scene's signs are square
  "+" plates, not octagons. A sign gets a detection of any class in only 64/387 visible frames, and those
  detections are mostly "chair" (50), "traffic light" (10) and "stop sign" (7). A stop-sign goal will rarely reach FOUND with the current model.
- Chairs are missed most at ≥ 1.9 m (73% detected) and when cut off very close (< 1.2 m, 75%).
