# Student A — Task 2: Platform, Scene, Camera, Motion Skills (60%)

You own the `skills/` folder (`skills_real.py`, the `SkillsAPI`
implementation everyone else's code depends on) and the scene assets under
`assets/scenes/` (`custom_scene.xml` + meshes). Nobody else edits inside
either.

You do **not** need to know anything about the LLM parser or YOLO to do
your job. Your only contract with the rest of the group is
`core.interfaces.SkillsAPI` — five methods. Implement them, test them on
your own, done. Run everything from the project root (`minilab_1_3/`).

## 1. Setup on your laptop

```bash
conda create -n quadruped_mujoco python=3.11 -y
conda activate quadruped_mujoco
git clone https://github.com/aoqianz/quadruped_mujoco.git
cd quadruped_mujoco && pip install -e .
pip install mujoco numpy onnxruntime pyyaml pillow ultralytics openai
cd ..
```

Confirm the demo works before touching any of the backbone code:

```bash
cd quadruped_mujoco
python eg/play.py                # native viewer: keyboard needs evdev (Linux only, not WSL)
python eg/play.py --gui          # browser panel at http://localhost:8765
```

### Browser panel keyboard shortcuts (WSL / no evdev)

Without `evdev` (e.g. on WSL2), the native viewer cannot read the keyboard,
and pressing keys in the MuJoCo window may crash it. Use the browser panel
instead (`python eg/play.py --gui`, then open http://localhost:8765 and click
on the page):

| Key | Action |
|-----|--------|
| W/S | forward / back |
| A/D | strafe left / right |
| Q/E | turn left / right |
| X   | E-Stop (same as the red **E-Stop** button) |
| T   | Reset Robot (same as the **Reset Robot** button) |

X and T require a one-line change to `src/runtime_control/panel.py`. If it
is not already in your copy, run this from the repository root
(`EE4705-mini_project/`):

```bash
python - <<'EOF'
from pathlib import Path
p = Path("quadruped_mujoco/src/runtime_control/panel.py")
s = p.read_text()
old = "actionKeys=new Map(Object.entries(customActions).filter(([k,v])=>v.shortcut).map(([k,v])=>[v.shortcut,k]));"
new = "actionKeys=new Map([['x','stop'],['t','reset'],...Object.entries(customActions).filter(([k,v])=>v.shortcut).map(([k,v])=>[v.shortcut,k])]);"
assert s.count(old) == 1, "line not found - already patched or file differs"
Path(str(p) + ".bak").write_text(s)
p.write_text(s.replace(old, new))
print("patched")
EOF
```

Check it worked:

```bash
grep -c "\['x','stop'\]" quadruped_mujoco/src/runtime_control/panel.py   # should print 1
```

After patching, restart `python eg/play.py --gui` and press **Ctrl+Shift+R**
in the browser to reload the page. R/F/Z/Y remain evdev-only; use the
panel's height controls instead.

If a GPU-less remote/headless box gives you a blank window: `export MUJOCO_GL=egl`.

## 2. What you're building

1. **Motion pipeline understanding** (goes in the report as a labeled
   block diagram): velocity command interface `(vx, vy, wz, body height)`
   → 46-dim observation + 6-frame history → ONNX policy at 50 Hz over
   200 Hz physics (decimation 4) → PD torque loop, and why the rear-leg
   joint remap between IsaacGym and MuJoCo ordering is needed.
2. **Camera pipeline** (already implemented — `skills_real.py`'s
   `_maybe_render_camera`, called once per iteration from the same
   `_sim_loop` background thread that steps physics/policy, not a
   separate thread): offscreen-renders `dog_front_camera` via its own
   `mujoco.Renderer` (wholly separate from whichever interactive viewer,
   browser panel or `--native`, is also open) at `core.config.CAMERA_HZ`
   = 15 Hz, inside the handout's recommended 10–20 Hz range — see the
   justification comment right on `CAMERA_HZ` in `core/config.py` and
   repeat/expand it in the report. The latest frame is exposed to the
   rest of the codebase (Task 4 in particular) via `get_camera_frame()`,
   which just returns the last frame that background thread published —
   it never renders synchronously inside the call.
3. **Scene**: your own MJCF with ≥3 objects from ≥2 COCO classes,
   including two same-class objects in different colors (e.g.
   `green_chair` / `red_chair`). Untextured primitives will NOT be
   detected by YOLO — use real meshes (Objaverse / Sketchfab). Save the
   scene file under `assets/scenes/`. Record each object's world `(x, y)`
   in `core.config.OBJECT_POSITIONS` using the `"<color>_<class>"` key —
   Student C's `[FOUND]` distance logging reads this directly.

   The current `assets/scenes/custom_scene.xml` builds on top of the
   example platform's own bundled `rc26_track` obstacle course rather
   than an empty scene — its terrain geoms were imported programmatically
   from `quadruped_mujoco/src/runtime_control/maps/26rc_track.xml`
   (registered upstream as `"rc26_track"` in
   `src/runtime_control/resources.py`; full citation in the scene file's
   own header comment), with the graded objects placed on top of it. If
   you replace this with your own from-scratch scene, keep
   `core.config.OBJECT_POSITIONS` in sync with wherever you actually put
   each object, and double-check clearance to any terrain you add —
   see `assets/scenes/README.md` for how the current positions were
   verified (a first attempt at placing objects on this terrain
   overlapped several of them with track geoms; positions were
   re-derived from an actual programmatic clearance scan, not eyeballed,
   after that).

   **⚠️ Current status: `custom_scene.xml`'s chairs/signs are still
   primitive geoms, exactly what the handout warns will fail YOLO
   detection.** The mesh-replacement scene is partway done — the mesh
   *files* have already been downloaded, but they are not yet sized,
   oriented, or switched on. Here's exactly where things stand and what's
   left, in order:

   **Already done:**
   - `assets/scenes/meshes/` already contains the real downloaded files:
     `chair.obj`, `stop_sign.obj`, `manifest.json` (records the Objaverse
     source + license for each, for the report's citation), plus their
     textures (`material.mtl`, `material_0.png`, `02_-_Default.png`).
   - `assets/scenes/custom_scene_meshes.xml` already exists and already
     points at those files correctly (`<mesh name="chair_mesh"
     file="chair.obj" .../>` etc., with `<compiler meshdir="meshes" />`
     telling MuJoCo where to look). It has the same terrain/positions/
     colors as `custom_scene.xml`, just with `<geom type="mesh">` object
     bodies instead of primitives.

   **Still left to do (needs a machine with MuJoCo + internet, not this
   sandbox):**
   1. Install the sizing tool and run it against both meshes:
      ```bash
      pip install trimesh numpy
      python tools/fit_mesh_scale.py assets/scenes/meshes/chair.obj --target-height 0.85
      python tools/fit_mesh_scale.py assets/scenes/meshes/stop_sign.obj --target-height 2.0
      ```
      Each prints the mesh's native bounding box and a computed uniform
      scale (`sx sy sz`) to make it a sensible real-world size.
   2. Paste those two computed scale values into
      `assets/scenes/custom_scene_meshes.xml`'s `<asset>` block, over the
      two placeholder lines that currently read `scale="1 1 1"` (one for
      `chair_mesh`, one for `stop_sign_mesh`).
   3. Test-load the scene (`RealSkills(scene_path=
      "assets/scenes/custom_scene_meshes.xml")`) and look at it in the
      browser panel. Adjust the six `euler="0 0 0"` placeholders — one on
      every `<geom type="mesh">` (two chair geoms, three sign-color
      geoms) — by eye, degree by degree, until each mesh stands upright
      and faces a sensible direction instead of lying on its side or
      upside down. Also check each object's floor contact: the body
      `pos` values assume the mesh's own bounding-box floor sits at
      `z=0`, which is rarely true for a downloaded mesh without a small
      z-offset adjustment.
   4. Once it visibly looks right, re-run the Task 4 debug-frames check
      to confirm YOLO detection actually improved on the real meshes —
      that's the entire point of this change, so don't skip the check.
   5. Only after step 4 looks good, flip `core.config.SCENE_PATH` from
      `"assets/scenes/custom_scene.xml"` to
      `"assets/scenes/custom_scene_meshes.xml"`.

   None of steps 1–4 have been run yet — they need `trimesh` and a real
   MuJoCo render, neither available in the sandbox that built this
   scaffolding. If you're picking this up for the first time: the mesh
   download is the part that needed real internet access and is already
   behind you; what's left is just numbers-in-a-script (step 1) and
   eyeballing a render (steps 3–4).
4. **Motion skills** — the two methods everyone else calls (see
   [`docs/DECISIONS.md`](DECISIONS.md) §2 for why these are two separate
   methods rather than one general `drive()`):
   - `move(vx, vy, wz, duration)`: timed velocity command, replaces
     `get_commands()` in `eg/play.py`, blocks until `duration` has
     elapsed in sim time.
   - `turn(angle_deg)`: **closed-loop**, using true yaw from
     `mj_data.qpos` (`atan2(2(wz+xy), 1-2(y²+z²))`), not open-loop
     timing. Must print
     `[TURN] target=<deg> final_error=<deg>` before returning.
     Include a short table/plot in the report showing why open-loop
     timing is inaccurate by comparison.

### Open-loop vs. closed-loop turn accuracy — collected data (n=24, FINAL)

**⚠️ Superseded data warning**: an earlier version of this section
quoted a 6-trial, 90°-only collection with a "22.98° mean error, ~13x
worse than closed-loop" headline. That number had a methodology bug —
it compared the open-loop move's **absolute final heading** to the
target, which only isolates the open-loop step by itself if the robot
started that step at yaw=0° (true for one early trial, not the general
case once trials chain `current_yaw + angle` back-to-back). **Use the
corrected numbers below instead** — see the full methodology
correction and all 24 raw trials in
[`docs/test_result/student_a_turn_accuracy_data.md`](test_result/student_a_turn_accuracy_data.md)
(the checklist below used to point at a `docs/turn_accuracy_data.md`
that doesn't exist — the real file is under `docs/test_result/`).

Reproduce with `python -m skills.skills_real --compare-turn --angles 45
90 180 --trials 6` (18 trials; the original single-pair 90°
`--compare-turn` collection is also still valid once re-analyzed with
the corrected formula — see the data file). Final summary, isolating
each open-loop move's own net rotation relative to where the preceding
closed-loop turn left the robot (`open_rotation = wrap(yaw_after_open −
yaw_after_closed)`), rather than its absolute final heading:

| Angle | Closed-loop mean error (deg) | Open-loop mean achieved rotation (deg) | Open-loop mean error (deg) | Fraction of target achieved |
|---|---|---|---|---|
| 45° | 1.52 | 12.65 | 32.35 | 28.1% |
| 90° | 1.80 | 23.95 | 66.05 | 26.6% |
| 180° | 1.57 | 45.67 | 134.33 | 25.4% |
| **Overall closed-loop (n=24)** | **1.67** | | | |

**Conclusion**: closed-loop `turn()` stays accurate across every angle
tested — mean error only 1.52–1.80° regardless of target size,
consistently close to its own 2° tolerance band (the tolerance setting,
not control noise, is the binding constraint). Open-loop timing does
**not** generalize at all: once measured correctly (isolating its own
net rotation, not folding in the preceding closed-loop turn), it
achieves only **~25–28% of the commanded angle at every target size
tested** — a consistent *multiplicative* shortfall, not a fixed
additive bias. A naive open-loop implementation that calibrates once
(at 90°) and linearly scales duration for other angles — exactly what
this test's own open-loop step does — inherits that same ~70–75%
shortfall at every other angle rather than correcting for it, proving a
single-point calibration cannot be extrapolated to other turn sizes.
**Headline numbers for the report: closed-loop mean error stays in the
1.5–1.8° range across 45°/90°/180° targets (24 trials total), while
open-loop timing achieves only ~25–28% of whatever angle is commanded —
a large, non-generalizing shortfall that true-yaw feedback fixes at
every angle tested, not just the one it happened to be calibrated
against.**

## 3. Where to write it

Everything is scaffolded in `skills/skills_real.py` — search for
`TODO(Student A)`. Don't change the method signatures (they're fixed by
`core.interfaces.SkillsAPI`); everything inside each method is yours.

## 4. Test entirely on your own

Before wiring up the real simulation, check that you understand the
contract you're implementing — run the same interface check Student B
and Student C's code will be held to, against the mock:

```bash
python tests/test_student_a.py
```

That only exercises `skills/skills_mock.py`; once `skills_real.py` has
real logic behind each method, the same checks (satisfies `SkillsAPI`,
`move()`/`turn()`/`stop()` don't raise, pose/camera-frame shapes are
right) are what your real implementation needs to keep passing too.

Then the actual keyboard-driven test:

```bash
python -m skills.skills_real
```

Wire up a keyboard test harness in the `if __name__ == "__main__":` block
(W/S/A/D/Q/E, plus a key to trigger a test `turn()`), exactly like the
demo in `eg/play.py`. You should be able to fully verify Task 2 —
walking, both cameras' views, both skills — without ever running
`llm_parser.py`, `navigation.py`, or `main.py`.

**Crouch / stand (body height) — CONFIRMED LIMITATION, read before using
this in the report.** `RealSkills.crouch()` / `.stand()` (and the
lower-level `set_height(height_cmd)` they call) write to `self._height_cmd`,
an input the ONNX policy reads every control tick (see
`build_single_obs`'s `height_cmd=` argument in `_sim_loop` and
`_warmup_obs`) — clamped into `self._height_range = (0.20, 0.35)`
meters, the same range handed to the browser panel's own height
slider. Bound to `c`/`t` in the keyboard harness above. **Not part of
`core.interfaces.SkillsAPI`** (that contract is frozen by group
agreement and Task 3/4 never need this), so it's a `RealSkills`-only
extra — `skills_mock.py` has matching print-only stubs.

A diagnostic run (`tools/visual_test_crouch_only.py`, which reads
`self._data.qpos[2]` via the new `get_trunk_height()` method
**before** any height command is ever sent) showed the trunk already
sitting at `trunk_z=0.329 m` immediately after boot — despite
`height_cmd` still being at its untouched 0.25 m default at that
point. Calling `crouch()` right after (target 0.20 m) then left
`trunk_z` completely unchanged, at 0.33 m, through every ramp step.
**Conclusion: the robot settles to ~0.33 m on its own after reset,
independent of `height_cmd` — the ONNX policy does not appear to use
`height_cmd` to control stance while standing still (zero velocity).**
This also reframes an earlier-looking "successful" `Stand`
(`trunk_z` 0.24→0.34 m) from a full end-to-end run: that was most
likely this same natural settling coinciding with the `Stand` call,
not `height_cmd` actually causing the change.

This is a policy/training limitation, not a bug in `crouch()`/
`set_height()`'s own logic — `set_height()` correctly computes,
ramps, and writes `height_cmd` every tick (confirmed by reading
`_sim_loop`), the value just doesn't appear to influence the standing
pose. `set_height()`'s per-step ramp and `[HEIGHT]` diagnostics are
kept as-is (they're harmless and still useful evidence), but don't
expect `crouch()`/`stand()` to visibly change the robot's stance while
it's standing still. If you want to push this further for the report,
try commanding a different `height_cmd` *while walking* (e.g. call
`set_height()` right before/during a `move()`) — if `height_cmd`
affects the gait's stance height during locomotion but not while
static, that would confirm the policy only uses it as a walking-gait
parameter, not a static-stance one; if it makes no difference there
either, `height_cmd` may not be functionally wired into this
particular trained policy at all. Either way, write up what the
`tools/visual_test_crouch_only.py` diagnostic actually showed (trunk_z
frozen at ~0.33 m regardless of `height_cmd`) rather than claiming
crouch/stand works — that's the honest, evidenced result.

Which direction is "crouch" vs "stand" (`height_range[0]` vs `[1]`) is
still just a naming-convention guess, now moot in practice since
neither visibly changes the standing trunk height — but the code is
left as originally structured (`crouch()` targets the lower bound,
`stand()` the upper) in case `height_cmd` turns out to matter during
locomotion and the direction needs confirming there instead.

**To test it**: `python tools/visual_test_crouch_only.py` (or
`--native`) is the definitive check — it prints `trunk_z` at boot,
*before* any height command, via `get_trunk_height()`, then calls
`crouch()` and prints the per-step `[HEIGHT]` lines after.

```bash
python tools/visual_test_crouch_only.py
python tools/visual_test_crouch_only.py --native
```

**Result on the team's WSL2 laptop (2026-09-30): `trunk_z=0.329 m`
already at boot, before `crouch()` was ever called, and unchanged
(`0.33 m`) after `crouch()` ran its full ramp down to a 0.20 m
target.** Confirms the finding above — see the "CONFIRMED LIMITATION"
callout — this isn't a code bug to keep chasing, it's the policy not
using `height_cmd` to control static standing height. Report this
result (the diagnostic script's actual printed numbers) rather than
re-running it hoping for a different outcome; it's deterministic given
the same policy/scene.

`python tools/visual_test_task2.py`'s fixed choreography still
includes a `Crouch`/`Stand` step pair (useful as a `Video_Task2`
source clip regardless), but don't expect to see a visible stance
change there either, for the same reason.

Also write the small verification script Task 2.iii asks for: render
frames of your scene from robot height, run YOLO on them, draw boxes,
and save one screenshot for the report — this doubles as your first
integration check with Student C's detector.

### High-speed movement: `run_fast()` and its test script

`RealSkills.run_fast(target_x, target_y, max_speed=1.0, ...)` is an extra
helper (like `crouch()`/`stand()`, not part of the frozen `SkillsAPI`
contract) for covering distance quickly: it ramps velocity up to
`max_speed` (accelerate), holds it (cruise), then ramps back down
(brake gently) while steering toward `(target_x, target_y)` — unlike
`move()`, which takes a fixed `(vx, vy, wz, duration)` and never adjusts
based on position. It has **no obstacle avoidance of its own**: it just
drives a straight line toward the target and will run into anything in
the way, the same as `move()`/`turn()` always have.

**Turn-settle behavior (fixed this round):** after a sharp turn
(>45°) inside `run_fast()`, the robot's yaw can keep drifting for a bit
even after the turn command finishes — a real run showed yaw still
moving 162.2°→172.7° several segments after a fixed, one-shot 0.3 s
pause. `run_fast()` now holds position in short 0.3 s bursts, re-checking
yaw drift between each burst, and keeps holding (up to 1.8 s total) until
the drift between consecutive bursts is under 1°, instead of a single
fixed-length pause. A later real run confirmed every big turn settles
cleanly now with no more "frozen position, still drifting" false-stuck
results.

`tools/visual_test_run_fast.py` is the test harness for `run_fast()` —
it drives the robot through a short tour of this project's graded
objects (`core.config.OBJECT_POSITIONS`), one at a time:

```bash
python tools/visual_test_run_fast.py                        # default: open_ground + red_stop sign
python tools/visual_test_run_fast.py --scenario "green_chair" "red_chair"
python tools/visual_test_run_fast.py --scenario all          # every graded object, in order
python tools/visual_test_run_fast.py --native                # native window instead of the browser panel
```

How each scenario works: the robot returns to a fixed staging point,
then approaches the object and stops `ARRIVAL_DISTANCE_M` (0.80 m — the
same "close enough" threshold Task 4 itself uses) short of it, counting
that as **reached**, then moves on to the next scenario (or ends, if it
was the last one). It is deliberately NOT a collision-course test
anymore — an earlier version of this script aimed straight through each
object on purpose, to find out whether `run_fast()` needed obstacle
avoidance (real runs confirmed it does collide if aimed directly at
something); that question is answered, so the script now treats getting
close as success instead of repeating the same crash every run.

Because `run_fast()` has no obstacle avoidance, the script itself has to
route every leg (return-to-staging, staging-to-object) around the OTHER
five objects and around the scene's terrain (stairs, the tilted plate,
rubble) using its own small path-planner (`_safe_route()` — tries a
direct line first, then a couple of L-shaped detours through the staging
point's column/row, each fully checked for clearance before being used).
If you add or move objects in the scene, keep `core.config.
OBJECT_POSITIONS` in sync — this script reads straight from it, so a
stale position will make it plan routes around the wrong spot.

### Terrain traversal: `climb_stairs()` / `cross_rough_terrain()` / `get_ground_height_below()`

Three more `RealSkills`-only extras (same deal as `crouch()`/`stand()`/
`run_fast()` — not part of the frozen `SkillsAPI` contract, so neither
Task 3's executor nor Task 4's `navigation.py` ever calls them directly).
They exist because `custom_scene.xml`'s imported `rc26_track` terrain
(two real staircases, `stairs_gentle`/`stairs_steep`, and a randomly-
tilted rubble patch) was never actually driven across or evaluated by
anything else in this project.

- **`get_ground_height_below(x=None, y=None)`**: the world-frame `z` of
  the terrain surface directly below world point `(x, y)` (defaults to
  the robot's own current position), found via a real downward MuJoCo
  raycast (`mujoco.mj_ray`) — **not** assumed to be `0.0`. **Cross-team
  dependency**: Student C's `navigation._camera_height_above_ground()`
  now calls this to correct the camera-to-target height estimate for
  local ground clearance (a flat-`z=0` assumption breaks as soon as the
  robot is standing on a staircase peak) — if you ever rename, remove,
  or change the return convention of this method, check `navigation.py`
  first, the same caution as changing anything else `SkillsAPI`-adjacent
  that another student's code has come to depend on.
- **`climb_stairs(target_x, target_y, width_axis=None, width_center=None,
  width_limit=None, segment_len=0.3, speed=0.3, recenter_gain=0.0,
  max_recenter_turn_deg=6.0, climb_height_cmd=None)`**: walk to a target
  across a staircase, re-facing it every short segment. Pass
  `width_axis`/`width_center`/`width_limit` for a strip with a real
  fall-off-the-side edge (e.g. `stairs_gentle`'s `y=2.0` strip); leave
  them unset for a structure with no edge to guard. Returns one of
  `"completed"`, `"edge_drift"` (drifted past the width guard),
  `"stuck"` (stopped making real progress — likely tipped/wedged), or
  `"incomplete"` (safety-cap segment count reached while still
  genuinely progressing). Only `"completed"` means it actually arrived;
  chain the next step only on that.
- **`cross_rough_terrain(target_x, target_y, segment_len=0.3,
  speed=0.3)`**: the same engine, for an open uneven patch (the rubble
  patch) with no edge to fall off — no width guard.
- Both are thin wrappers around a shared private engine
  (`_walk_terrain_segment_loop()` + `_face_waypoint()`) that: re-faces
  the target before every segment (a single uncorrected step-edge yaw
  nudge otherwise compounds into drifting off the structure); flags a
  single-segment trunk-height *delta* above `max_height_jump` as a
  likely stumble (not an absolute-height check, since standing on an
  elevated peak is correctly a high absolute reading); aborts
  `"edge_drift"`/`"stuck"` as above; and keeps walking until the robot
  actually **arrives**, rather than giving up after a fixed, precomputed
  segment count (a real climb — re-facing every segment eats into
  forward progress — can need several times the naive straight-line
  segment estimate).
- **Real-run finding worth citing in the report**: `recenter_gain`
  (an explicit cross-track correction term, meant to pull the robot
  back toward `width_center` when it drifts) defaults to `0.0`
  (**off**). Three real runs on `stairs_steep`'s own crossing told a
  consistent story: the plain, uncorrected version drifted off-center
  but still climbed real height and safely self-aborted on
  `edge_drift`; turning recentering on, at two different gains, both
  made it *worse* — one caused a real stumble (trunk_z jumped +0.176 m
  in one segment, ending `"stuck"`), the other stalled the robot almost
  immediately (barely any forward progress, never clearing the first
  riser). Interrupting a tall-riser climbing gait with extra turn
  commands — even small, capped ones — looks to break its rhythm more
  than the uncorrected lateral drift itself hurts. Pass
  `recenter_gain > 0` explicitly to opt back in; see `_face_waypoint`'s
  own docstring in `skills_real.py` for the full numbers from all three
  runs.
- **`climb_height_cmd` caveat**: there is no exposed control anywhere in
  this codebase over how high a foot swings mid-stride — that's
  entirely internal to the trained ONNX policy. Raising `height_cmd`
  toward the top of the trained range before a climb (the default
  behavior unless you pass `climb_height_cmd=False`) is only a *proxy*
  — a taller commanded standing stance *might* give the legs more
  extension margin — whether it actually changes real step clearance
  during a climb is **unverified**.
- **Test harness**: `tools/visual_test_rough_terrain.py` exercises all
  three real terrain features by world coordinate, read directly off
  `custom_scene.xml`. Default (`python tools/visual_test_rough_terrain.py`,
  no flags) now runs **rubble only** — `stairs_steep` is opt-in
  (`--feature stairs_steep`) since every real run of its own climb so
  far has ended `"stuck"` or `"edge_drift"`; `--feature all` runs the
  full canonical three in one process. See that script's own module
  docstring for the full run-by-run history (it's extensive — this
  terrain work went through several real-hardware-adjacent iterations).
- This also underpins the optional advanced-requirement scenario Task 4
  can claim: `blue_chair` sits on `stairs_gentle`'s own peak, not
  reachable by a flat-ground `goto_object()` call — see
  `tools/visual_test_blue_chair_stairs.py`, which climbs it via
  `climb_stairs()` before handing off to Student C's `goto_object()`
  for the final vision-based approach/stop.

### Watch it run in the simulation

`tools/visual_test_task2.py` boots the real `RealSkills` (`gui=True`)
and runs a fixed, unattended choreography — forward, strafe, a
closed-loop turn, forward, another turn, stop — printing the pose
before/after each step, instead of you live-typing keys:

```bash
python tools/visual_test_task2.py
```

Open the browser panel it starts (same one `--gui` already uses) to
actually watch the robot. Because the sequence is fixed and repeatable,
it's also a convenient source clip for `Video_Task2` — re-run it as many
times as you need for a clean take.

Pass `--native` instead to open a native MuJoCo window rather than the
browser panel — no server/port needed. This script's fixed, scripted
sequence itself (walk/strafe/turn/crouch/stand) has run cleanly under
`--native`. **Exit is not reliably clean, though**: a
"Segmentation fault (core dumped)" has been observed right after
Ctrl+C on at least one run, immediately after the printed
"Shutting down..." line — i.e. during `skills.shutdown()`'s own
native-viewer teardown, not before it, so it isn't the older
`skills.stop()`-didn't-clean-up bug (that one is fixed; `shutdown()`
now joins the sim thread before closing the native viewer, on
purpose, so nothing is still calling into GLFW from the background
thread during teardown). No Python traceback is produced, so this
hasn't been root-caused — treat it as in the same unresolved-native-
crash family as the interactive `python -m skills.skills_real
--native` segfault below, not a new, unrelated bug. The run's printed
data (`[HEIGHT]`/`[TURN]`/pose lines) is still valid evidence even
when the exit itself crashes. Use `--gui` if you need a guaranteed-
clean exit; see the
[student guide](STUDENT_README.md#browser-panel-or-native-viewer) for
the current, more cautious guidance. `--gui`/`--native` are mutually
exclusive.

```bash
python tools/visual_test_task2.py --native
```

`tools/check_status.py` is a separate, faster sanity check (no
simulation): it scans `skills/skills_real.py` and
`assets/scenes/custom_scene.xml` for leftover `NotImplementedError`/TODO
markers and runs `tests/test_student_a.py` for you.

```bash
python tools/check_status.py
```

## 5. Handing off to the group

Once `python -m skills.skills_real` works standalone:

```python
# main.py
USE_REAL_SKILLS = True
```

Nothing else changes. Student B's and Student C's code should keep
working unmodified against your real implementation, because they were
only ever written against `core.interfaces.SkillsAPI`.

## 6. Deliverables checklist (Task 2)

Status below reflects what's actually in this repo as of 2026-10-04 —
re-check before submitting, since this file isn't updated automatically.

- [x] Block diagram + explanation of the control pipeline in the report
      — **not in this repo**; this is report content, lives outside the
      codebase (confirm with the team whether it's written elsewhere)
- [x] Camera pipeline running at a stated, justified rate — done,
      `CAMERA_HZ = 15` in `core/config.py`, justified inline (§2.2 above)
- [x] Scene file with ≥3 objects, ≥2 COCO classes, one same-class color
      pair — done, 6 objects in `custom_scene.xml` (chairs, stop signs,
      a sports ball); **but see the ⚠️ mesh status above** — they're
      still primitive geoms, which the handout says YOLO won't detect
- [x] `object_positions` config filled in — done, `core.config.
      OBJECT_POSITIONS` matches the scene file exactly
- [x] `move()` and `turn()` implemented and keyboard-tested — done, no
      `TODO(Student A)`/`NotImplementedError` left in `skills_real.py`;
      `turn()` prints the required `[TURN]` line
- [x] Table/plot: open-loop vs. closed-loop turn accuracy — done, see
      `docs/test_result/student_a_turn_accuracy_data.md` (the data file
      actually in this repo — not `docs/turn_accuracy_data.md`, a path
      this checklist used to cite that doesn't exist). **FINAL, 24
      trials across 45°/90°/180°** (supersedes an earlier, methodology-
      flawed 6-trial/90°-only write-up): closed-loop mean error
      1.52–1.80° at every angle tested; open-loop achieves only
      ~25–28% of whatever angle is commanded — see the summary table
      and corrected methodology in §2 above
- [x] Terrain traversal (optional advanced-requirement groundwork) —
      done, `climb_stairs()`/`cross_rough_terrain()`/
      `get_ground_height_below()` in `skills_real.py`, exercised by
      `tools/visual_test_rough_terrain.py` (default: rubble only;
      `stairs_gentle` completes cleanly, `stairs_steep` still ends
      `stuck`/`edge_drift` on every real run so far) — see §2 above.
      This is what Task 4's optional `blue_chair`-on-`stairs_gentle`
      scenario builds on
- [x] `Video_Task2`: scene + objects, onboard camera view, a timed move,
      a closed-loop turn with `[TURN]` visible — **not in this repo**;
      no video file found. `tools/visual_test_task2.py`'s choreography
      (forward/strafe/turn/crouch/stand) is a ready-made source clip for
      this once you record your screen running it
