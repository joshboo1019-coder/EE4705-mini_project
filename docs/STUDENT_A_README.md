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
   detection** — see `assets/scenes/README.md`'s "Known risk" section
   for the full explanation and a prepared (but not yet finished) fix:

```bash
   # On a machine with real internet access (this sandbox has none to
   # Objaverse/Sketchfab), not this one:
   pip install objaverse trimesh
   python tools/fetch_scene_meshes.py
   python tools/fit_mesh_scale.py assets/scenes/meshes/chair.obj --target-height 0.85
   python tools/fit_mesh_scale.py assets/scenes/meshes/stop_sign.obj --target-height 2.0
```

   That downloads real Objaverse-LVIS-tagged chair/sign meshes and tells
   you the MJCF `<mesh scale="..."/>` to use. `assets/scenes/custom_scene_meshes.xml`
   is already scaffolded with the same terrain/positions/colors as
   `custom_scene.xml`, just with `<geom type="mesh">` object bodies
   instead of primitives — it has exactly two kinds of placeholder left
   for you to fill in by hand:
   - Two `scale="1 1 1"` placeholders in the `<asset>` block (one for
     `chair_mesh`, one for `stop_sign_mesh`) — replace each with the
     `sx sy sz` triple `fit_mesh_scale.py` prints for that mesh.
   - Six `euler="0 0 0"` placeholders, one on every
     `<geom type="mesh">` (two chair geoms, three sign geoms, both
     colors of each) — adjust each by eye, after test-loading the
     scene, until the mesh stands upright and faces a sensible
     direction; also re-check floor contact (each object body's `pos`
     assumes the mesh's own bounding-box floor sits at `z=0`, which is
     rarely true for a downloaded mesh without adjustment).

   Once it visibly looks right, re-run the Task 4 debug-frames check to
   confirm YOLO detection actually improved before flipping
   `core.config.SCENE_PATH` over to it. None of this has been run or
   verified yet — it's scaffolding for you to finish on your own
   machine.
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

### Open-loop vs. closed-loop turn accuracy — collected data (n=6)

Run `python skills_real.py --compare-turn` (from inside `skills/`,
headless — no `--gui`/`--native` needed) to reproduce: it does one
closed-loop `turn(90.0)` followed by one open-loop
`move(vx=0.0, vy=0.0, wz=0.6, duration=1.5)` (a fixed timing/rate guess
with no feedback), both targeting 90 deg. 6 trials collected on the
team's WSL2 laptop (`LAPTOP-6LL3JIIS`), 2026-09-30:

| Trial | Closed-loop yaw (deg) | Closed-loop \|error\| (deg) | Open-loop yaw (deg) | Open-loop \|error\| (deg) |
|---|---|---|---|---|
| 1 | 88.12 | 1.88 | 112.5 | 22.5 |
| 2 | 88.04 | 1.96 | 112.5 | 22.5 |
| 3 | 88.21 | 1.79 | 112.8 | 22.8 |
| 4 | 88.53 | 1.47 | 114.5 | 24.5 |
| 5 | 88.21 | 1.79 | 112.9 | 22.9 |
| 6 | 88.04 | 1.96 | 112.7 | 22.7 |
| **mean (n=6)** | | **1.81** | | **22.98** |
| **min / max** | | 1.47 / 1.96 | | 22.50 / 24.50 |

**Conclusion**: closed-loop `turn()` converges to a mean error of
**1.81 deg** (tightly clustered, spread of only 0.49 deg across all 6
trials — consistent with its own 2 deg tolerance being the binding
constraint, not control noise). Open-loop `move()` produced a mean
error of **22.98 deg** — roughly **13x** larger. This is overwhelmingly
a **systematic bias**, not random noise: 5 of 6 trials landed within a
0.4 deg band of each other (112.5, 112.5, 112.7, 112.8, 112.9 deg),
meaning the `1.5s @ wz=0.6 -> 90 deg` assumption is consistently
*wrong* by a fixed amount for this platform's real turning dynamics —
exactly the kind of miscalibration open-loop control has no way to
detect or correct, and that closed-loop control eliminates by
construction (it measures true yaw and corrects toward it regardless
of the underlying turning rate). **Headline numbers for the report:
closed-loop mean error 1.81 deg vs. open-loop mean error 22.98 deg
(n=6 each) — a ~13x accuracy improvement from closing the loop on true
yaw feedback.**

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

- [ ] Block diagram + explanation of the control pipeline in the report
- [ ] Camera pipeline running at a stated, justified rate
- [ ] Scene file with ≥3 objects, ≥2 COCO classes, one same-class color pair
- [ ] `object_positions` config filled in
- [ ] `move()` and `turn()` implemented and keyboard-tested
- [ ] Table/plot: open-loop vs. closed-loop turn accuracy
- [ ] `Video_Task2`: scene + objects, onboard camera view, a timed move,
      a closed-loop turn with `[TURN]` visibleal
