# Student C — Task 4: YOLO Detection, Color Grounding, Search & Approach (60%)

You own the entire `perception/` folder: `perception_real.py`,
`navigation.py`. It's your own directory — nobody else edits inside it.

You do **not** need Student A's simulation running or Student B's LLM
parser finished. `perception_real.py` only needs image arrays in, and
`navigation.py` only talks to `core.interfaces.SkillsAPI` /
`core.interfaces.PerceptionAPI`. Develop against `skills/skills_mock.py`
and saved test images first. Run everything from the project root
(`minilab_1_3/`).

## 1. Setup on your laptop

```bash
conda create -n quadruped_mujoco python=3.11 -y
conda activate quadruped_mujoco
pip install ultralytics opencv-python numpy pillow
```

The first `ultralytics` import will auto-download the YOLO weights
(`core.config.YOLO_MODEL`, default `yolo11n.pt`) — do this once while you have
internet, it's cached afterward. CPU inference at the resolutions used
here is real-time on a laptop; no GPU needed.

## 2. What you're building

1. **`perception_real.RealPerception.detect(frame)`** — runs YOLO on a
   camera frame, then determines each detection's color from the pixels
   inside its bounding box (e.g. median hue in HSV via `cv2.cvtColor`).
   Do **not** expect YOLO to know colors — that's on you. Print
   `[DETECT] class=... color=... conf=... bbox=...` for each detection.
   Design your test scene's objects (with Student A) around classes
   YOLO's 80 COCO classes can actually detect — untextured boxes will
   not register as "chair".

   The current `_grounded_color()` has two robustness tweaks worth
   knowing about if a color still looks wrong: it shrinks the bbox 15%
   in from every edge before sampling (a loose box on a thin-legged
   prop like a chair otherwise lets background bleed in through the
   gaps and skew the read — this is what caused an early "chair reads
   blue instead of green" bug), and classifies by the **mode** of a
   10°-wide hue histogram rather than the median, logging
   `hue/sat/val/n_valid_px` on every `[DETECT]` line so a bad read is
   visible in the console instead of silently averaged away. Use
   `tools/visual_test_task4.py --debug-frames DIR` (see below) if you
   need to see the exact pixels a detection's color came from.
2. **`navigation.goto_object(class, color, skills, perception)`** — the
   search/steer/approach state machine (why this lives here and not in
   `dialogue/`: [`docs/DECISIONS.md`](DECISIONS.md) §3):
   - not visible → print `[SEARCH] target not visible, rotating`, turn,
     re-detect (count consecutive misses to debounce camera shake —
     `core.config.MAX_MISSES_BEFORE_LOST`)
   - visible → steer so the bbox center moves toward the image center
     (`_steer_to_center` — proportional control on `wz`), then step
     forward
   - "found" only when **all** of: (C1) detected in the live frame at
     the moment of stopping, (C2) planar distance to object ≤ 0.80 m
     (`core.config.FOUND_DISTANCE_M`), (C3) logged via `[FOUND]`. Ground-truth
     `core.config.OBJECT_POSITIONS` may be read **only** to compute that
     logged distance — never inside the steering logic itself (see
     [`docs/DECISIONS.md`](DECISIONS.md) §4 for why that's kept a plain
     config constant instead of part of `PerceptionAPI`).
   - full turn with no detection, or timeout (`core.config.APPROACH_TIMEOUT_S`,
     default 60 s) → `[MISSION] status=FAIL reason=...`
   - success → `[MISSION] status=SUCCESS`

## 3. Test entirely on your own

```bash
# perception, against a saved image — no sim needed
python -m perception.perception_real --image test_frame.png

# navigation state machine, against MockSkills — no sim needed
python tests/test_student_c.py
```

`MockPerception` (already provided) returns "not found" for the first
couple of calls and then a detection, so the navigation test exercises
both the `[SEARCH]` branch and the `[FOUND]`/steering branch without
needing your real detector finished yet either. Get a few frames from
Student A early (even before their sim is fully wired) to validate
detection on your actual scene objects — that's the Task 2.iii/4.ii
"verify detection early" screenshot for the report.

### Watch it run in the simulation

`tools/visual_test_task4.py` boots the real `RealSkills` + real
`RealPerception` and calls `navigation.goto_object()` directly against
the objects placed in `assets/scenes/custom_scene.xml`, so you can watch
the `[SEARCH]`/`[DETECT]`/`[FOUND]`/`[MISSION]` sequence happen live,
without needing Student B's LLM parser finished at all:

```bash
python tools/visual_test_task4.py --class chair --color green
python tools/visual_test_task4.py --class "stop sign" --color red
python tools/visual_test_task4.py --mock-perception   # state-machine only, no YOLO
```

`--mock-perception` swaps in `MockPerception` so you can verify the
search/steer/approach *logic* even before `perception_real.py`'s
`detect()` is finished — it can't verify real detection or color
grounding that way, only the navigation state machine.

Other flags worth knowing:

```bash
python tools/visual_test_task4.py --camera dog_front_camera   # default: robot POV, the same feed detect() sees
python tools/visual_test_task4.py --camera tracking           # third-person instead
python tools/visual_test_task4.py --debug-frames /tmp/color_debug   # dump every frame + bbox crop as PNGs
python tools/visual_test_task4.py --native                    # native MuJoCo window instead of the browser panel
```

`--debug-frames DIR` saves the full camera frame and each detection's
(shrunk) bbox crop as PNGs under `DIR`, alongside the hue/sat/val stats
already logged on `[DETECT]` — the fastest way to check a suspicious
color result against the actual pixels instead of guessing. `--native`
opens a native MuJoCo window instead of the browser panel; it also
respects `--camera`, switching the native window to whichever fixed
camera you asked for. `--gui`/`--native` are mutually exclusive.

**`--native` has an open issue specific to this script.** It's fine for
Task 2/Task 3-with-mock-perception, but for this script (or Task 3 with
`--real-perception`) — anything that calls `get_camera_frame()` — the
offscreen renderer that feeds it can start silently returning the same
stale frame on every call once the native window is also open, likely a
GL-context conflict between the two in one process. The symptom: normal
`[SEARCH]`/`[TURN]` lines, then `[DETECT]` locks onto one bbox that
barely moves for the rest of the run even though the robot keeps
rotating, ending in `[MISSION] status=FAIL reason=timeout`. A
`[CAMERA] render failed ...` console line confirms it's happening (this
used to fail completely silently — fixed to at least log now). Until
this is resolved, use the default browser panel for this script.

`tools/check_status.py` is a separate, faster sanity check (no
simulation): it scans `perception/perception_real.py` and
`perception/navigation.py` for leftover `NotImplementedError`/TODO
markers.

```bash
python tools/check_status.py
```

## 4. Handing off to the group

No changes needed elsewhere — `navigation.py` and `perception_real.py`
were written entirely against the interfaces. Once your standalone tests
pass:

```python
# main.py
USE_REAL_PERCEPTION = True
```

## 5. Deliverables checklist (Task 4)

- [ ] Detection method (YOLO + color grounding approach) summarized/justified in report
- [ ] `[DETECT]` lines with class, color, confidence, bbox
- [ ] `goto_object()` implements search, steer-to-center, approach, stop
- [ ] `[FOUND]` only fires under C1–C3; ground truth used for logging only
- [ ] `[MISSION] status=FAIL reason=...` after full-turn-no-detection or timeout
- [ ] ≥10-trial evaluation: detection accuracy, grounding accuracy,
      approach success rate, final distance `d`, failure analysis —
      including ≥1 not-initially-visible case and ≥1 same-class
      disambiguation (green vs. red chair) — table in the report
- [ ] `Video_Task4`: terminal visible throughout, typed command visible,
      `[CMD]` / `[SEARCH]` / `[DETECT]` / `[FOUND]` / `[MISSION]` lines,
      for ≥2 objects including one not-initially-visible and one
      same-class disambiguation
      