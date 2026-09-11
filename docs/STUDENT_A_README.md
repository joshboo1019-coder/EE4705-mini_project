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
python eg/play.py                # native viewer — W/S/A/D/Q/E/R/F/T
python eg/play.py --gui          # browser panel at http://localhost:8765
```

If a GPU-less remote/headless box gives you a blank window: `export MUJOCO_GL=egl`.

## 2. What you're building

1. **Motion pipeline understanding** (goes in the report as a labeled
   block diagram): velocity command interface `(vx, vy, wz, body height)`
   → 46-dim observation + 6-frame history → ONNX policy at 50 Hz over
   200 Hz physics (decimation 4) → PD torque loop, and why the rear-leg
   joint remap between IsaacGym and MuJoCo ordering is needed.
2. **Camera pipeline**: offscreen-render `dog_front_camera` at 10–20 Hz
   (`core.config.CAMERA_HZ`) in a background thread — see the `_camera_loop`
   TODO in `skills_real.py`. State and justify your chosen rate in the
   report.
3. **Scene**: your own MJCF with ≥3 objects from ≥2 COCO classes,
   including two same-class objects in different colors (e.g.
   `green_chair` / `red_chair`). Untextured primitives will NOT be
   detected by YOLO — use real meshes (Objaverse / Sketchfab). Save the
   scene file under `assets/scenes/`. Record each object's world `(x, y)`
   in `core.config.OBJECT_POSITIONS` using the `"<color>_<class>"` key —
   Student C's `[FOUND]` distance logging reads this directly.
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

Also write the small verification script Task 2.iii asks for: render
frames of your scene from robot height, run YOLO on them, draw boxes,
and save one screenshot for the report — this doubles as your first
integration check with Student C's detector.

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
      a closed-loop turn with `[TURN]` visible in the terminal
