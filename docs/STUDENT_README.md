# Student Guide — MiniLab 1.3 Backbone

**Start here if you're new to this codebase.** For your own task's
setup/build/test/checklist, jump to your guide: [A](STUDENT_A_README.md) ·
[B](STUDENT_B_README.md) · [C](STUDENT_C_README.md).

Our goal is to make a simulated quadruped follow typed English commands
such as:

> "walk forward for three seconds, then turn back" — then later —
> "go to the green chair"

We split this into three jobs:

| Student | Your job in simple words | Example output | Main file to edit |
| --- | --- | --- | --- |
| **A — Task 2: platform** | Set up the simulated robot, its camera, the scene, and the two motion moves (a timed move and a closed-loop turn) everyone else calls. | `[TURN] target=180.0 deg final_error=1.8 deg` | `skills/skills_real.py` |
| **B — Task 3: dialogue (your role)** | Turn one typed English sentence into an ordered list of robot actions, run them, and keep the chat responsive. | `[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2` | `dialogue/llm_parser.py`, `dialogue/executor.py`, `dialogue/chat_interface.py` |
| **C — Task 4: perception** | Detect objects and their colors in the camera feed, then search for and approach the requested one. | `[FOUND] class=chair color=green t=14.2 s d=0.61 m` | `perception/perception_real.py`, `perception/navigation.py` |

All three students also share Task 1 (comparing LLM-to-robot approaches, in
the report) and Task 5 (integration, videos, submission). See the handout.

**You can start separately.** A does not need to know anything about the
LLM parser. B can develop against a mock robot and a mock detector before
A's simulation or C's YOLO detector exist. C can develop the search/steer
logic against that same mock robot before A's simulation exists either.

## The idea

Three people cannot productively edit one simulation loop at once. So the
whole codebase is split two ways at once, and they reinforce each other:

1. **By folder, one per task** — `skills/` (Task 2), `dialogue/` (Task 3),
   `perception/` (Task 4) — so each student has their own directory and
   never needs to edit someone else's files.
2. **By interface** — `core/interfaces.py` defines two abstract classes,
   `SkillsAPI` and `PerceptionAPI`. Student A's `skills/` folder and
   Student C's `perception/` folder each implement one; Student B's
   `dialogue/` folder (the parser, executor, chat loop) only ever talks
   to those two interfaces — never to MuJoCo or YOLO directly.

That combination means:

- Student B can build and fully test the entire command pipeline today,
  using `skills/skills_mock.py` / `perception/perception_mock.py` as
  stand-ins, without waiting for the simulation or the detector to exist.
- Student C can build and test `perception/navigation.py`'s
  search/steer/approach logic against `skills/skills_mock.py` too, and
  can build/test `perception/perception_real.py` against saved test
  images — independent of both A and B.
- Student A can build and keyboard-test `skills/skills_real.py`
  completely on its own (`python -m skills.skills_real`), with no
  knowledge of the LLM parser or YOLO at all.

Integration is then a five-minute step: flip `USE_REAL_SKILLS` and
`USE_REAL_PERCEPTION` to `True` in `main.py` once each real module passes
its own standalone test. Nobody has to touch anyone else's folder to do this.

## Day one (10-minute kickoff, all three present)

1. Confirm `core/schema.py`'s command shapes match what you'll actually need.
2. Confirm `core/interfaces.py`'s two abstract classes are enough — add
   methods now if you already know you'll need them; changing them later
   means re-touching two people's folders (see
   [`docs/DECISIONS.md`](DECISIONS.md) for why they're shaped this way).
3. Agree on `core/config.OBJECT_POSITIONS` key convention (`"<color>_<class>"`).
4. Check the shared backbone works before anyone writes task-specific code:

```bash
python -m pytest -q tests/
```

`test_student_a.py`, `test_architecture.py`, and `test_handoff.py` are
pytest-discoverable and should all **pass** on day one — they only
exercise the mocks and the wiring, nothing Student B or C have written
yet. `test_student_b.py` and `test_student_c.py` are plain scripts (run
them directly, not through pytest — see below); on day one they're
expected to stop with a `NotImplementedError` at the one TODO each
depends on (`_call_llm` for B, `_steer_to_center` for C). That's the
correct starting state, not a bug.

5. Split and go — from here on, each student mostly lives inside their
   own folder. First commands (run from the project root):

```bash
# Student A
python tests/test_student_a.py          # contract check against the mock
python -m skills.skills_real            # once implemented

# Student B
python tests/test_student_b.py

# Student C
python tests/test_student_c.py
python -m perception.perception_real --image test_frame.png
```

## Integration order (suggested)

1. Student A finishes `skills/skills_real.py` -> flip `USE_REAL_SKILLS = True`
   in `main.py`, re-run Student B's and C's mock-based tests against the
   real sim — they should still pass since nothing but the flag changed.
2. Student C finishes `perception/perception_real.py` -> flip
   `USE_REAL_PERCEPTION = True`.
3. Run `python main.py` end-to-end for the reference scenario in the
   handout (walk-forward-then-turn, then go-to-the-green-chair).
4. Record `Video_Task2`, `Video_Task3`, `Video_Task4` per the spec.

## What NOT to do

- Don't import `skills.skills_real` or `perception.perception_real` from
  anywhere except `main.py` — that coupling is exactly what breaks
  parallel development (`tests/test_architecture.py` enforces this).
- Don't compute `goto_object`'s "found" decision from
  `core.config.OBJECT_POSITIONS` — that dict is for the `[FOUND]`
  distance log and evaluation only (see the handout's Definition of
  "found", C1-C3).
- Don't edit `core/schema.py` / `core/interfaces.py` solo — a silent
  field rename breaks the other two people's folders without a merge
  conflict to warn you.

## Common problems

| What you see | What to do |
| --- | --- |
| `ModuleNotFoundError: No module named 'core'` | Run from the project root (`minilab_1_3/`), not from inside a subfolder |
| `ModuleNotFoundError: No module named 'mujoco'` (or similar) | Activate the conda env and re-run `pip install -r requirements.txt` / `pip install -e ".[dev]"` |
| No MuJoCo viewer window appears | Normal on a headless/remote box; set `MUJOCO_GL=egl` (or `osmesa` as a slower fallback) |
| `NotImplementedError` from `_call_llm` / `_steer_to_center` | Expected until Student B / Student C implement their TODO — see their guide |
| `openai`/API error when running the chat loop | Check the exported API key env var and that `core.config.LLM_SERVICE` matches a service you've configured — see the [B guide](STUDENT_B_README.md) |
| YOLO detects nothing on your scene | Untextured MJCF primitives don't register as COCO classes — use real meshes (Objaverse/Sketchfab), see the [A guide](STUDENT_A_README.md) |
| `[MISSION] status=FAIL reason=timeout` every time | Check `_steer_to_center`'s centering tolerance and `config.APPROACH_TIMEOUT_S` before assuming the detector is at fault |
| `pytest` fails collecting `test_student_b.py` / `test_student_c.py` | Expected — they're plain scripts, not pytest test files; run them directly (`python tests/test_student_b.py`) |
| Integration flag flipped but `main.py` still uses the mock | Check you edited `USE_REAL_SKILLS` / `USE_REAL_PERCEPTION` in `main.py` itself, not a local copy |

Owner: backbone (ALL).
