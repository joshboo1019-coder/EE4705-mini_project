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

**Crouch / stand (body height)**: `RealSkills.crouch()` / `.stand()` (and
the lower-level `set_height(height_cmd)` they call) change the trunk-
height command the ONNX policy reads every control tick
(`self._height_cmd`, previously set once at `__init__` and never
touched again) — clamped into `self._height_range = (0.20, 0.35)`
meters, the same range handed to the browser panel's own height
slider. Bound to `c`/`t` in the keyboard harness above. Each call
prints a `[HEIGHT] target=... trunk_z_before=... trunk_z_after=...`
line using the trunk's actual measured world-frame z
(`self._data.qpos[2]`) — that's your evidence it physically changed,
not just that a number was set. **Not part of `core.interfaces.
SkillsAPI`** (that contract is frozen by group agreement and Task 3/4
never need this), so it's a `RealSkills`-only extra, called directly —
`skills_mock.py` has matching print-only stubs so code written against
it doesn't break if you switch back to the mock.

Which direction is "crouch" vs "stand" (`height_range[0]` vs `[1]`) is
a guess from the naming convention, not something verified by actually
running the sim — watch the browser panel when you test it, and if
`crouch()` visibly stands taller instead of crouching down, the two
are simply swapped from what was guessed; flip which bound each method
targets in `skills_real.py`.

**To test it**: either the keyboard harness (`c` / `t`, watch the pose
change in the browser panel and the printed `trunk_z` values), or run
`python tools/visual_test_task2.py`, whose fixed choreography now
includes a crouch step followed by a stand step near the end — a
repeatable, unattended way to check it (and a source clip for
`Video_Task2` showing it).

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
browser panel — no server/port needed. Confirmed working end-to-end
(full sequence + clean Ctrl+C exit) on WSL2 **for this specific
scripted, non-interactive sequence** — `--native` has since segfaulted
(unresolved, no Python traceback) on the interactive
`python -m skills.skills_real --native` keyboard harness on the same
machine, so don't assume `--native` is safe everywhere just because
this script's fixed sequence ran clean; see the
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
