# Hard scene: an optional stress test for Task 4

*Student B (assist), branch `assist/hard-scene`, pending review by Student C (Task 4) and
Student A (scene). This scene is optional. The default scene `assets/scenes/custom_scene.xml`
and `config.SCENE_PATH` are unchanged.*

`main.py --scene hard` loads `assets/scenes/custom_scene_hard.xml`. That file is the default scene
copied verbatim (terrain and all graded objects), with five extra bodies, and it dims the lighting
at runtime. It tests the parts of Task 4 that the default scene and C's 10 scenarios never
exercise:

| Change | Where | What it stresses |
|---|---|---|
| A second green chair, `green_chair_2`, identical to `green_chair` | (-3.5, 1.1), next to the orange ball | Ambiguity: the parser has no way to say *which* green chair. `_pick_target` takes the first match in YOLO's list. Body lookup is covered in §2. |
| `wall_north`: 1.2 m high, 10 cm thick, grey | x = -4.0, y ∈ [1.45, 3.05] | Occlusion: hides the yellow stop sign from the spawn. The search only rotates in place and never explores. |
| `wall_south` (same size) | x = -4.0, y ∈ [-3.05, -1.45] | Hides the green stop sign from the spawn. |
| `orange_box`: 0.4 m cube with the ball's rgba | (-3.6, -0.9) | Colour distractor. Not a COCO target; it should never be reported as an orange ball. |
| `red_box`: 0.4 m cube with the red chair's rgba | (-2.3, -3.1) | Colour distractor near the red chair. |
| Lighting × 0.55: every light plus the headlight's diffuse, ambient and specular | runtime (`hard_scene.apply_lighting`) | Detection and HSV colour grounding under dimmer, flatter light. |

The `--scene hard` and `--scenario N` flags are **mutually exclusive**, because a scenario builds
its own scene from the default one. `--gt-instance KEY#N` is valid only together with
`--scene hard`. Its only effect is to choose which instance the log lines measure to (§2).

## 1. Layout

Top view, 0.25 m per column and 0.5 m per row. `@` is the spawn at (0, 0), facing +x (to the
right). All objects are at x < 0, behind the robot.

```
        -5  -4  -3  -2  -1   0      x (m)
 +3.5 |                          |
 +3.0 |      #                   |   #  wall_north / wall_south (1.2 m)
 +2.5 |      #                   |   G  green_chair#1 (-2.0, 2.0)  default scene
 +2.0 |    Y #       G           |   g  green_chair#2 (-3.5, 1.1)  NEW
 +1.5 |      #                   |   R  red_chair     (-2.0,-2.0)
 +1.0 |        g                 |   o  orange ball   (-3.5, 0.0)
 +0.5 |                          |   r  red stop sign (-1.3, 0.0)
 +0.0 |        o        r    @   |   Y  yellow stop sign (-4.5, 2.0)  hidden by wall_north
 -0.5 |                          |   S  green stop sign  (-4.5,-2.0)  hidden by wall_south
 -1.0 |        b                 |   b  orange_box (-3.6,-0.9)  distractor
 -1.5 |      #                   |   x  red_box    (-2.3,-3.1)  distractor
 -2.0 |    S #       R           |   (blue_chair stays on the stairs at (3.45, 2.0))
 -2.5 |      #                   |
 -3.0 |      #      x            |
 -3.5 |                          |
```

All additions lie inside the free region that C's scenarios use (x ∈ [-6, -1], |y| ≤ 3.5), and the
nearest track geom is at least 2 m away. Each wall has open floor at one end: north of
`wall_north` and south of `wall_south`, the floor is open with no terrain anywhere at x < -2.6. The
2.9 m gap between the walls holds the ball, green chair #2 and the orange box. The routes from
the spawn to every visible target are unchanged from the default scene, since the walls and boxes
all sit behind their targets as seen from the spawn. `python -m perception.hard_scene` validates
the layout and prints a 2-D line-of-sight check from the spawn: the yellow and green stop signs
are **hidden** and every other target is **visible**.

Ground truth is used **for logging and evaluation only**. It lives in `perception/hard_scene.py`:
`OBJECT_POSITIONS_HARD` holds the keys `green_chair#1` and `green_chair#2` plus the plain keys for
the other targets. `DISTRACTORS_HARD` and `WALLS_HARD` hold the extra bodies. `tests/test_hard_scene.py`
checks that the XML and these tables agree.

## 2. Two green chairs vs. `navigation._find_target_body_id`

`goto_object` reads the target's live height through `_camera_height_above_ground`, which calls
`_find_target_body_id(model, color, class)`. That function groups geoms by body. It keeps a body
when the body's **material name**, split on `_`, contains the colour token, and either the
material also contains a class token or the geometry matches the class (a chair has ≥ 4 boxes). If
two bodies match, it raises `LookupError("Multiple simulator bodies match ...")`. A plain copy of
the chair would therefore crash every "go to the green chair" at its first range estimate.

**What I did (navigation.py is unchanged):** the second chair uses its own material,
`chair_green2_mat`, with the same rgba (`0.10 0.55 0.15 1`). After compose_scene the name becomes
`custom_scene_chair_green2_mat`, whose tokens are `{custom, scene, chair, green2, mat}`. There is
no `green` token, so the lookup returns exactly one body: green chair #1. Both chairs stand on the
floor, so the height navigation reads from #1 (seat centre 0.44 m) is also correct for #2. The
height is the only thing navigation takes from that body. Perception sees pixels, not materials,
so to YOLO and the HSV grounding the two chairs are identical.

The headless check compiles both variants (`tools/hard_scene_check.py`, step 1):

| Scene | `_find_target_body_id(green, chair)` | Every other target |
|---|---|---|
| hard (`chair_green2_mat`) | one body at (-2.0, 2.0) | correct body and position |
| naive (2nd chair reuses `chair_green_mat`) | `LookupError: Multiple simulator bodies match color='green', class='chair': [1, 8]` | correct |

After `RealSkills(gui=False, scene_path=hard)` boots, `_camera_height_above_ground` and
`_ground_truth_distance` run without error for all 7 targets: green, red and blue chair, ball, and
red, yellow and green stop sign.

*Possible future patch for C (not applied).* To make the lookup tolerate duplicate instances in
general, `_find_target_body_id` could return the first candidate when every candidate has the same
body z, because the height is the only use:
`if len(candidates) > 1 and len({round(float(model.body_pos[b][2]), 3) for b in candidates}) == 1: return candidates[0]`.
The naming trick makes this unnecessary for the hard scene.

**What `[FOUND] d=` and `[RANGE] ground_truth=` mean with two green chairs.** Both lines use
`config.OBJECT_POSITIONS["green_chair"]`, which holds a single position. `--scene hard` swaps
`config.OBJECT_POSITIONS` in memory, the same way `scenarios.apply_to_config` does, and maps
`green_chair` to **green chair #1 (-2.0, 2.0)** by default. With `--gt-instance green_chair#2` it
maps to #2 (-3.5, 1.1) instead. These lines therefore give the distance to *that* instance,
whichever chair the robot actually approached. The S6 evaluator does not trust them: it
recomputes the true distance to **every** instance from the trace and reports both `went_to`
(the nearest instance) and the distance to the intended instance.

## 3. Lighting

`runtime_control.map_manager.compose_scene()` imports only `<geom>` and `<body>` elements from a
map file. Lights and `<visual>` come from the robot XML (`dog_terrain.xml`: one directional light
with diffuse 1, and a headlight with diffuse 0.6 and ambient 0.3). A `<light>` or `<headlight>`
placed in the scene XML would therefore be dropped silently. Instead,
`hard_scene.apply_lighting(skills)` scales `model.light_{diffuse,ambient,specular}` and
`model.vis.headlight.*` in place by `LIGHT_SCALE = 0.55` right after the sim boots. The change is
render-only: the headlight becomes diffuse 0.33 and ambient 0.17. It applies to the onboard camera
and to the browser panel, because both render the same model.

## 4. Headless findings (`tools/hard_scene_check.py`)

Command: `QUADRUPED_MUJOCO_ROOT=… eval/run_env.sh tools/hard_scene_check.py`. It runs one
`RealSkills(gui=False)`, uses no port, teleports the robot with `scenarios.place_robot`, and runs
`RealPerception.detect` at the default `YOLO_CONF_THRESHOLD = 0.2`. The images and the raw JSON are
in `docs/report_assets/hard_scene/`. Each `*_full_vs_dim.png` shows full light on the left and ×0.55
on the right.

**Spawn sweep (×0.55 light, 12 headings: the in-place search).** File: `spawn_sweep_dim.png`.

| Heading | Detections (colour class conf) |
|---|---|
| 0–60 | blue chair 0.50–0.93 (on the stairs) |
| 90 | green chair 0.35 (green chair #1 at the left edge), "unknown bench" (stairs) |
| 120 | green chair 0.88 (#1), green chair 0.69 (#2) |
| 150 | **green chair 0.83 (#2), green chair 0.82 (#1)**, orange ball 0.75 |
| 180 | green chair 0.67 (#1), red chair 0.56, green chair 0.53 (#2) |
| 210 | red chair 0.73, green chair 0.60, orange ball 0.57 |
| 240–270 | red chair 0.31–0.67, "unknown bench" |
| 300–330 | none |

* **The occluders work.** Neither the yellow nor the green stop sign is detected at any heading
  (the 2-D line-of-sight check agrees). The red stop sign at (-1.3, 0) is not detected from the
  spawn either, but the walls are not the cause: its face, 1.3 m away, is above the top edge of the
  camera frame. That geometry is the same in the default scene.
* **The yellow sign stays hard to detect even when it is not occluded.** It is not detected from
  behind `wall_north` on a diagonal (pose D, about 1.5 m; the "+"-shaped sign face is axis-aligned)
  or square-on from between the walls (pose E, about 2.3 m), even at full light. S6_05 is therefore
  expected to fail on two counts: the wall, and weak recall for the yellow sign. Only the first is
  new in this scene.
* **Ambiguity is real.** From the spawn, both green chairs are in view together from heading 120
  to 210, with nearly equal confidence (0.83 vs 0.82 at heading 150). `_pick_target` takes YOLO's
  first, highest-confidence match on every frame, so the chosen chair can switch between frames.
  The first green chair the left-turning search detects is #1, at heading 90.
* **The boxes are never detected**, as anything, at ×0.55 or at full light. Both are visible in
  the frames: the orange box at headings 150–210 and in pose A, the red box beside the red chair in
  pose B. As colour distractors they are therefore inert to YOLO at the scene's lighting. They
  would matter only if a box were misdetected, or if a box and a target fell inside one bounding
  box (see ×0.15 below).

**Fixed poses at full light, ×0.55 (the scene setting), ×0.3 and ×0.15.** Mean frame luma falls
from 70–75 to 56–60, then 39–43, then 29–33. Detections are listed for the intended objects.

| Pose (x, y, yaw) | Full | ×0.55 | ×0.3 | ×0.15 |
|---|---|---|---|---|
| S spawn (0, 0, 180) | green chair 0.73 / red chair 0.36 / green chair 0.28 | 0.63 / 0.56 / 0.50 | 0.62 / 0.56 / 0.55 | all three **"unknown chair"** |
| A (-2.2, -0.5, 170): ball, orange box, green chair #2 | ball 0.90, green chair 0.52 | 0.89, 0.76 | 0.92, 0.75 | ball 0.90, "unknown chair", **"orange chair" 0.27 = the orange box** |
| B (-1.0, -1.5, 215): red chair, red box | red chair 0.47 | 0.64 | 0.59 | red chair 0.69 **+ a 2nd "red chair" 0.26** |
| C (-1.0, 1.0, 160): both green chairs | 0.61 / 0.51, ball 0.41 | 0.76 / 0.75, ball 0.59 | 0.77 / 0.76, ball 0.66 | both "unknown chair" |
| D (-5.8, 0.4, 51): behind wall_north | green chair #2 0.84; yellow sign not detected | 0.93 | 0.93 | "unknown chair" |
| E (-4.6, -0.3, 90): yellow sign square-on | green chair 0.52; yellow sign not detected | 0.81 | 0.85 | "unknown chair" |

* **At ×0.55, the dim light does not hurt detection.** Every object detected at full light is
  still detected with the correct colour. Chair confidences mostly *rise*, because the flatter
  shading of the primitive props looks more chair-like. The far green chair at the spawn goes
  from 0.28 to 0.50, and the red chair from 0.36 to 0.56.
* **Teleport crash risk (harness only).** One of the four check runs segfaulted during the sweep.
  `scenarios.place_robot` writes `qpos` and calls `mj_forward` from the main thread while the sim
  thread is stepping, and MuJoCo is not thread-safe. Rerunning the check worked. S6 does not
  teleport: every trial starts at the normal spawn.
* **The breaking point lies between ×0.3 and ×0.15**, and colour grounding fails before YOLO
  does. At ×0.15 the chairs are still detected, but their colour becomes `unknown` because pixels
  fall below the saturation and value gates in `_grounded_color`. The distractor boxes then begin
  to appear as chairs (an "orange chair" and a second "red chair"). If the scene should be made
  harder, ×0.2 would be the setting that stresses colour grounding.

## 5. S6: typed goto trials on the hard scene (not run here)

`eval/e2e/run_all.py --suites S6` launches `eval/run_env.sh main.py --gui --scene hard` once per
trial, from a fresh sim, types the utterance, and scores it like S3. The true distance comes from
the trace (logging only) and is measured to the **intended** instance, at the time of the first
`[MISSION]` line. Measuring then gives the right answer even when the parser splits an utterance
into two goals. Trace contacts are labelled with their body (`wall_north`, `red_box`, …) through
`hard_scene.geom_labels()`.

| Trial | Typed | Intended | Expected | Stress |
|---|---|---|---|---|
| S6_01_green_ambiguous | go to the green chair | either green chair | SUCCESS | which chair is chosen, and whether the choice switches mid-approach |
| S6_02_green_by_ball (`--gt-instance green_chair#2`) | go to the green chair next to the orange ball | green_chair#2 | SUCCESS (record the parse) | the `goto_object` schema cannot express "next to", so the parse may drop the qualifier or make it a second goal |
| S6_03_red_chair_red_box | go to the red chair | red_chair | SUCCESS | red box distractor |
| S6_04_ball_orange_box | go to the orange ball | orange ball | SUCCESS | orange box distractor |
| S6_05_occluded_yellow_sign | find the yellow stop sign | yellow sign | FAIL:target_not_found | occluded by wall_north; the search does not explore |
| S6_06_red_sign_dim | go to the red stop sign | red stop sign | SUCCESS | control: dim light only |

The summary table reports the `[CMD]` line, the mission result, the estimated distance at the stop,
`went_to` with the true distance to each instance, the true distance to the intended instance,
C1, C2, detections whose colour/class pair does not exist in the scene (for example
`orange/chair`, which would be a box misdetection), labelled contacts, and falls.

**Run it** only when nothing else holds port 8765. The trials use `--gui`, and recordings go to
`~/Videos/e2e/`.

```
QUADRUPED_MUJOCO_ROOT=/home/jiamo/EE4705/quadruped_mujoco \
  eval/run_env.sh eval/e2e/run_all.py --suites S6 --label hard_scene
# one trial:   ... --suites S6 --only S6_02_green_by_ball
# re-score:    eval/run_env.sh eval/e2e/run_all.py --reeval eval/e2e/results/<run>
```

Predictions from the headless check, to be confirmed by the real run:
* S6_01 probably approaches #1, because the search meets it first, but it may switch to #2 while
  turning towards it.
* S6_02 is likely to fail or to be scored on whichever chair the robot happens to reach.
* S6_03, S6_04 and S6_06 should behave as they do in the default scene.
* S6_05 should report `FAIL reason=target_not_found` after a full 360° turn.

## Files

* `assets/scenes/custom_scene_hard.xml`: the scene. It was generated once from `custom_scene.xml`
  and is checked into the repo. If the default scene changes, re-copy it and re-append the five
  bodies; `tests/test_hard_scene.py` fails if the copies drift apart.
* `perception/hard_scene.py`: ground truth (logging only), `apply_to_config`, `apply_lighting`,
  `geom_labels`, and layout validation.
* `main.py`: the `--scene {default,hard}` and `--gt-instance` flags.
* `eval/e2e/run_all.py`: the S6 suite, `_eval_s6`, and the S6 summary section.
* `tools/hard_scene_check.py`: the headless check (§2, §4).
* `tests/test_hard_scene.py`: no-sim tests covering the XML against the ground truth, the default
  bodies kept unchanged, the body lookup, config swapping, flag conflicts, lighting, and S6 scoring.
