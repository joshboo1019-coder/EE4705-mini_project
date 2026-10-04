# MiniLab 1.3 — Backbone
<!-- Change contributed by Student B (assist), pending review by the group: install/run steps re-checked on a fresh clone (docs/REPRODUCE.md) -->
 
Owner: backbone (ALL)
 
Shared infrastructure for the LLM + YOLO powered quadruped mini-lab: frozen
data contracts (`core/`), the Task 2 motion-skills interface (`skills/`,
Student A), the Task 3 LLM dialogue/parsing/execution loop (`dialogue/`,
Student B), and the Task 4 perception + search-and-approach interface
(`perception/`, Student C) — wired together in `main.py`.
 
**Students: start with the [student guide](docs/STUDENT_README.md).** It
explains the split, a day-one kickoff checklist, and the integration order.
Then go to your own task guide: [A guide](docs/STUDENT_A_README.md) ·
[B guide](docs/STUDENT_B_README.md) · [C guide](docs/STUDENT_C_README.md).
Contract choices and the reasoning behind them are recorded in
[`docs/DECISIONS.md`](docs/DECISIONS.md).
 
## Installation
 
This works on Linux natively; on Windows use WSL2 (the browser control
panel makes the GUI usable over WSL2). No GPU is needed — everything but
the LLM call runs on CPU.
 
```bash
# 0. Clone this repo and the example platform SIDE BY SIDE — eval/run_env.sh
#    looks for ../quadruped_mujoco (override with $QUADRUPED_MUJOCO_ROOT).
#    Skip the platform if your group chose a different one (Section V of the
#    handout) and point skills/skills_real.py's TODOs at its API instead.
git clone https://github.com/joshboo1019-coder/EE4705-mini_project.git
git clone https://github.com/aoqianz/quadruped_mujoco.git
cd EE4705-mini_project
 
# 1. Environment: a venv at .venv/ (eval/run_env.sh runs .venv/bin/python)
python3 -m venv .venv            # Python >= 3.11 (fresh-clone check: 3.13.5)
source .venv/bin/activate
unset PYTHONPATH                 # if ROS set it — it breaks the venv and pytest
 
# 2. Platform + this backbone's dependencies
pip install -e ../quadruped_mujoco
pip install -r requirements.txt  # pulls torch via ultralytics: ~6 GB in .venv/
```
 
Conda also works (`conda create -n quadruped_mujoco python=3.11 -y`, then
the two `pip install` lines), but `eval/run_env.sh` only uses `.venv/`: with
conda, run the commands below as plain `python ...` from the repo root with
`PYTHONPATH` unset and `MUJOCO_GL=egl` exported. Use `requirements.txt`
rather than `pip install -e ".[dev]"` — the pyproject extras lack
`python-dotenv` (reads `.env`) and `faster-whisper` (voice input).
 
The YOLO weights (`core.config.YOLO_MODEL` = `yolo11n.pt`, ~5.6 MB) are
downloaded automatically into the repo root the first time `RealPerception`
is built (internet needed once; `*.pt` is git-ignored). Each student's own
guide has task-specific setup.
 
## API configuration (Task 3 only)
 
Offline development and every mock-based test need no API key. The live
LLM parser (and the `look` VLM) does. `dialogue/llm_parser.py` reads each key
from the environment first, then from a git-ignored `.env` in the repo root
(next to `main.py`). Never commit it:
 
```bash
# .env — only the provider behind core/config.LLM_SERVICE / VLM_SERVICE is needed
DASHSCOPE_API_KEY=...   # Alibaba Model Studio, international region (default qwen-flash, qwen3-vl-flash)
GOOGLE_API_KEY=...      # Gemini
OPENAI_API_KEY=...      # OpenAI
```
 
A key exported in your shell overrides `.env`. Without a valid key everything
still starts; each typed command is just rejected with
`[CMD] rejected reason=llm_error:...`.
 
See [the B guide](docs/STUDENT_B_README.md) for which services to compare
and how `core/config.LLM_SERVICE` selects between them.
 
## What this repository contains
 
Source for the four packages below, mock implementations and tests for
isolated development, scene assets, and per-task student guides. Course
submission zips separately add the report, demo videos, and any exported
scene meshes — see the handout's submission instructions. Build the zip with
`tools/make_submission_zip.sh <commit> --video demo.mp4 --report report.pdf
--out DIR`: it packs `minilab_1.3_group_9.zip` from `git archive <commit>`
(so `.env`, `.venv/` and `*.pt` never ship), drops files over 5 MB under
`eval/results/` and `docs/` unless `--keep PATH`, and aborts if anything looks
like an API key.
 
Run everything from the repo root through `eval/run_env.sh` (unsets
`PYTHONPATH`, sets `QUADRUPED_MUJOCO_ROOT` and `MUJOCO_GL=egl`, uses
`.venv/bin/python`). Tests are split one file per student, plus two
backbone-owned checks:
 
```bash
eval/run_env.sh -m pytest -q tests/                  # everything, offline (fake LLM), ~40 s
eval/run_env.sh tests/test_student_a.py              # A's SkillsAPI contract, against the mock
eval/run_env.sh tests/test_student_b.py              # B's parser+executor, mocked A & C — LIVE LLM, needs a key
eval/run_env.sh tests/test_student_c.py              # C's nav logic, mocked A
eval/run_env.sh -m pytest -q tests/test_architecture.py   # enforces the dialogue/ import boundary
eval/run_env.sh -m pytest -q tests/test_handoff.py        # main.py's wiring (real flags on: boots headless sim + YOLO)
```
 
Known failures on a fresh clone of `main` are listed in
[`docs/REPRODUCE.md`](docs/REPRODUCE.md).
 
And the standalone / real-module commands (all headless unless `--gui`):
 
```bash
eval/run_env.sh -m skills.skills_real                 # A's real sim: type w/s/a/d/q/e/c/t/p, `quit` exits
eval/run_env.sh -m skills.skills_real --compare-turn  # A's closed- vs open-loop turn numbers
cp docs/test_result/camera_evidence/20hz/frame_0119.png /tmp/frame.png
eval/run_env.sh -m perception.perception_real --image /tmp/frame.png  # C's detector -> /tmp/frame_detections.{jpg,json}
eval/run_env.sh eval/mock_main.py                     # B's chat loop on mock A & C (live LLM)
eval/run_env.sh main.py                               # full system, headless: type commands, Ctrl+C quits
eval/run_env.sh main.py --gui                         # same + browser panel at http://localhost:8765
```
 
## Directory ownership and student entry points
 
```
core/        backbone (ALL)   — schema.py, interfaces.py, config.py (frozen contracts)
assets/      Student A        — scenes/: MJCF scene file + meshes
skills/      Student A        — Task 2: implement SkillsAPI in skills/skills_real.py
dialogue/    Student B        — Task 3: llm_parser.py, executor.py, chat_interface.py
perception/  Student C        — Task 4: implement PerceptionAPI in perception/perception_real.py,
                                 plus navigation.py (search & approach)
tests/       backbone (ALL)   — one test file per student, plus test_architecture.py
                                 (import-boundary check) and test_handoff.py (integration)
docs/        backbone (ALL)   — student guide, per-task guides, design decisions
main.py      backbone (ALL)   — wires real vs. mock modules together at integration time
```
 
Student entry points: implement the ABCs in `core/interfaces.py`
(`SkillsAPI` in `skills/skills_real.py`, `PerceptionAPI` in
`perception/perception_real.py`), keep the class names (`RealSkills`,
`RealPerception`), and flip the matching flag in `main.py`
(`USE_REAL_SKILLS`, `USE_REAL_PERCEPTION`) to `True` once real. Student B's
`dialogue/` modules must not import `skills.skills_real` or
`perception.perception_real` directly — they only ever see the interfaces,
via whichever implementation `main.py` wires in.
 
## Contract evolution rules
 
- `core/schema.py` / `core/interfaces.py` changes require agreement of all
  three students; after freezing, only **add** new fields or methods —
  never remove or repurpose existing ones.
- Bump `core.schema.CONTRACT_VERSION` on any semantic change (new required
  field, removed field, changed meaning); note the change in
  [`docs/DECISIONS.md`](docs/DECISIONS.md). Purely additive fields don't
  need a bump.
- Cross-module data passes only through `core/schema.py` dataclasses —
  `dialogue/` never imports `skills.skills_real` or
  `perception.perception_real` directly, only the interfaces they satisfy
  (`tests/test_architecture.py` enforces this mechanically).
- Ground-truth data in `core/config.OBJECT_POSITIONS` may be read only for
  logging/evaluation (the `[FOUND]` distance) — never inside steering or
  detection logic.
