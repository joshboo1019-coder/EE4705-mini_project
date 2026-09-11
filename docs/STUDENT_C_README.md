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
