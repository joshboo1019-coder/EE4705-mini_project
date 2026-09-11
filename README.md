# MiniLab 1.3 — Backbone

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
# 1. Environment
conda create -n quadruped_mujoco python=3.11 -y
conda activate quadruped_mujoco

# 2. Example platform (skip if your group chose a different platform —
#    see Section V of the handout for alternatives, and point skills/
#    skills_real.py's TODOs at your platform's API instead)
git clone https://github.com/aoqianz/quadruped_mujoco.git
cd quadruped_mujoco && pip install -e .
cd ..

# 3. This backbone's dependencies (either works)
pip install -r requirements.txt
# or: pip install -e ".[dev]"
```

Tested with Python 3.11. Each student's own guide has setup specific to
their task (API keys for Task 3, the YOLO weight download for Task 4, etc).

## API configuration (Task 3 only)

Offline development and every mock-based test need no API key. The live
LLM parser does. Export credentials as environment variables — never
commit them:

```bash
export OPENAI_API_KEY=...
export DASHSCOPE_API_KEY=...      # Alibaba Cloud (Qwen)
export GOOGLE_API_KEY=...         # Gemini
```

See [the B guide](docs/STUDENT_B_README.md) for which services to compare
and how `core/config.LLM_SERVICE` selects between them.

## What this repository contains

Source for the four packages below, mock implementations and tests for
isolated development, scene assets, and per-task student guides. Course
submission zips separately add the report, demo videos, and any exported
scene meshes — see the handout's submission instructions.

Tests are split one file per student, plus two backbone-owned checks:

```bash
python -m pytest -q tests/                  # everything below, in one go
python tests/test_student_a.py              # A's SkillsAPI contract, against the mock
python tests/test_student_b.py              # B's parser+executor pipeline, mocked A & C
python tests/test_student_c.py              # C's nav logic, mocked A
python -m pytest -q tests/test_architecture.py   # enforces the dialogue/ import boundary
python -m pytest -q tests/test_handoff.py        # main.py's own real-vs-mock wiring, end to end
```

And the standalone / real-module commands:

```bash
python -m skills.skills_real                                 # Student A's real sim, standalone
python -m perception.perception_real --image test_frame.png  # Student C's real detector
python main.py                                                # full system once all three are wired in
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
