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
#    run_env.sh checks for the platform on every run except --mock.
#    Graders: clone the submitted tag (--branch final-r6), not the default branch.
#    Skip the platform if your group chose a different one (Section V of the
#    handout) and point skills/skills_real.py's TODOs at its API instead.
git clone --branch final-r6 https://github.com/joshboo1019-coder/EE4705-mini_project.git
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

If the platform is not the sibling `../quadruped_mujoco` (e.g. you cloned
it somewhere else), export its path before every `eval/run_env.sh` call:
`export QUADRUPED_MUJOCO_ROOT=/path/to/quadruped_mujoco` (and use that path
in the `pip install -e` line).

Conda also works (`conda create -n quadruped_mujoco python=3.11 -y`, then
the two `pip install` lines), but `eval/run_env.sh` only uses `.venv/`: with
conda, run the commands below as plain `python ...` from the repo root with
`PYTHONPATH` unset and `MUJOCO_GL=egl` exported. Use `requirements.txt`
rather than `pip install -e ".[dev]"` — the pyproject extras lack
`python-dotenv` (reads `.env`) and `faster-whisper` (voice input).

**Walking policy and robot model are not in this repo.** `skills/skills_real.py`
loads the platform's ONNX locomotion policy, robot MJCF and config
(`DEFAULT_ONNX`, `DEFAULT_ROBOT_XML`, `DEFAULT_CONFIG` from `eg/play.py`) out of
the `quadruped_mujoco` clone, found via `$QUADRUPED_MUJOCO_ROOT` (default: the
sibling `../quadruped_mujoco`, set by `eval/run_env.sh`). The submission zip
does not vendor it either: clone it as in step 0. Our own scene (world,
objects, meshes) is in `assets/scenes/`; the ten Task 4 layouts are in
`perception/scenarios.py`.

The YOLO weights (`core.config.YOLO_MODEL` = `yolo11n.pt`, ~5.6 MB) are
downloaded automatically into the repo root the first time `RealPerception`
is built (internet needed once; `*.pt` is git-ignored). Each student's own
guide has task-specific setup.

## API configuration (Task 3 only)

Offline development and every mock-based test need no API key. The live
LLM parser (and the `look` VLM) does. `dialogue/llm_parser.py` reads each key
from the environment first, then from a git-ignored `.env` in the repo root
(next to `main.py`). Start from the placeholder template and never commit
the real file (`.env` is git-ignored, `.env.example` is not):

```bash
cp .env.example .env    # then replace your-key-here for the provider you use
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

## Running the system (`main.py`)

Always through `eval/run_env.sh` from the repo root. Type English commands at
the prompt ("walk forward 1 m", "turn left 90 degrees", "go to the red
chair", "look: what is in front of you?"); `v` + Enter records a spoken command
(bonus, needs a microphone); Ctrl+C quits, and so does Ctrl+D / the end of
piped input, after the queued commands have run (`[CHAT] input closed (EOF)`),
e.g. `printf 'go to the green chair\n' | eval/run_env.sh main.py --scenario 3`.

| Flag | Effect |
|---|---|
| *(none)* | real sim (headless, EGL) + YOLO + live LLM |
| `--gui` | same, plus the browser control panel at http://localhost:8765 (real skills only) |
| `--native` | native MuJoCo window instead of the browser panel (real skills only; `run_env.sh` then keeps GLFW instead of EGL) |
| `--scenario N` | Task 4: object layout + robot start pose `N` (1–10 or a name) from `perception/scenarios.py`; the scene is written to a temp dir |
| `--mock` | `MockSkills` + `MockPerception`: no sim, no YOLO (the LLM is still live) |

```bash
eval/run_env.sh main.py --gui                  # demo used for Video_Task3 / Video_Bonus
eval/run_env.sh main.py --gui --scenario 3     # Task 4 layout 3, then e.g. "go to the green chair"
eval/run_env.sh main.py --scenario 3           # same, headless (no browser panel, no port 8765)
eval/run_env.sh main.py --mock                 # parser + executor only
eval/run_env.sh -m perception.task4_cli --scenario 3   # C's standalone Task 4 prompt (no LLM)
```

Headless boot prints one `[CAMERA] render failed (EGLError ... EGL_BAD_ACCESS ...)`
line; the renderer is recreated and later frames are fine (see `eval/run_env.sh`).
The first real-perception run downloads `yolo11n.pt` (~5.4 MB) into the repo root.
Non-interactive example (one LLM call, then the run is stopped):

```bash
(sleep 45; echo "go to the green chair"; sleep 60) | timeout 120 eval/run_env.sh main.py --scenario 3
```

## What this repository contains

Source for the four packages below, mock implementations and tests for
isolated development, scene assets, and per-task student guides. Course
submission zips separately add the report, demo videos, and any exported
scene meshes — see the handout's submission instructions. Build the zip
from the final **tag** (never the working tree):

```bash
tools/make_submission_zip.sh --tag final \
    --task2 Video_Task2.mp4 --task3 Video_Task3.mp4 --task4 Video_Task4.mp4 \
    --bonus Video_Bonus.mp4 --report report.pdf --out ~/submit
tools/make_submission_zip.sh --tag HEAD --draft --out /tmp/zipcheck   # dry run: lists what is missing
```

It writes `minilab_1.3_group_9.zip` (`--name` overrides; the handout's example
is `project_1.3_group_<N>.zip`) with the four videos at the zip root under
exactly those names, the report PDF under its own file name, and the repo tree
from `git archive <tag>`: `.env`, `.venv/`, `*.pt`, `*.pyc`, tracked `*.mp4`,
voice `*.wav` and raw e2e traces (`eval/e2e/results/*/` keeps only
`summary.md` and `*.csv`) never ship; files over 5 MB under `eval/results/`
and `docs/` are dropped unless `--keep PATH`. A missing video or report is an
error unless `--draft`. The zip's contents are scanned for API keys (any hit:
`file:line` printed, zip deleted, exit 1); the listing (top 2 levels) and size
are printed at the end.

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

On the `final-r3`..`final-r6` tags the whole offline suite passes (290 passed, 1 xfailed,
~31 s). [`docs/REPRODUCE.md`](docs/REPRODUCE.md) records an EARLIER
fresh-clone check of `main` (95 passed, 6 failed, segfault) and is
historical only.

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

## Evaluations

Offline unless marked LIVE (API key, costs money) or SIM (real MuJoCo, a few
minutes). Results land in `eval/results/` (Task 3), `eval/e2e/results/<run>/`
(e2e) and `docs/report_assets/` (Task 2 / Task 4).

```bash
# Unit / contract tests (fake LLM, no sim): 290 passed, 1 xfailed
eval/run_env.sh -m pytest -q tests/
eval/run_env.sh -m pytest -q tests/test_no_ground_truth.py   # no OBJECT_POSITIONS / xpos in decision code

# Task 3 parser accuracy (B) — LIVE
eval/run_env.sh eval/task3_eval.py --ping                     # one call per service
eval/run_env.sh eval/task3_eval.py --set standard --services qwen-flash gpt-5-nano --prompt v5 --runs 3   # v5 = llm_parser.SYSTEM_PROMPT
eval/run_env.sh eval/task3_eval.py --set hard --services qwen-flash --prompt v5 --runs 1 --budget 0.2
eval/run_env.sh eval/task3_eval.py --report                   # offline: rebuild eval/results/summary.md
eval/run_env.sh eval/ablation.py --services qwen-flash gpt-5-nano --modes json_schema tools --budget 0.05
eval/run_env.sh eval/upgrade_report.py                        # offline: eval/upgrade_eval.md tables + PNGs

# Bonus: speech input (B) — needs a microphone and a human speaker
eval/run_env.sh eval/stt_eval.py                              # record + score
eval/run_env.sh eval/stt_eval.py --rescore eval/results/stt/<session>
eval/run_env.sh eval/stt_eval.py --report eval/results/stt/<session>.jsonl

# End-to-end on the real sim (B harness) — SIM + LIVE; needs Xvfb (virtual display :99)
eval/run_env.sh eval/e2e/run_all.py --suites S1 S2 S3 S4 --label final
eval/run_env.sh eval/e2e/run_all.py --suites S5 S7 --label upgrades --no-video
eval/run_env.sh eval/e2e/run_all.py --reeval eval/e2e/results/<run>          # offline re-score
eval/run_env.sh eval/e2e/compare.py <baseline_run> <final_run> --out eval/e2e/COMPARISON.md

# Task 2 turn accuracy (A; scripts by B assist) — SIM
eval/run_env.sh tools/task2_turn_trials.py --angles 45 90 180 --trials 6 \
    --modes closed open_A open_cal --out docs/report_assets/task2/logs/turn_trials_left.jsonl
eval/run_env.sh tools/task2_turn_report.py                     # offline: table + figure

# Task 4 colour grounding test set (C; script by B assist) — render is SIM, the rest offline
eval/run_env.sh tools/task4_color_testset.py render --out /tmp/colorset [--holdout]
eval/run_env.sh tools/task4_color_testset.py detect --out /tmp/colorset [--model yolo11s.pt]
eval/run_env.sh tools/task4_color_testset.py score  --out /tmp/colorset
```

e2e suites: S1 Task 2 skills (closed/open-loop turn, move), S2 the Task 3
video script, S3 the ten Task 4 scenarios through `main.py --scenario`, S4
bonus look + multi-goal, S5 Task 3 upgrades (e-stop, return home, status,
programs, out-of-range, non-English), S7 blue chair on the stairs. S6 (hard
scene) exists only on the unmerged `assist/hard-scene` branch; its run is in
`eval/e2e/results/20261004-0247_hard_scene/`.

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

## Contribution table

Videos recorded by B on the final tag; code ownership per contribution table.

Every source file starts with an `Owner:` line (or `STUDENT X OWNS THIS
FILE`), and files outside B's area that B changed carry `Change contributed by
Student B (assist), pending review by Student X`. Derived from those headers
and the commit tags (`git log --format=%s -- <file>`: `[B]`, `[assist A]`,
`[assist C]`, `[ALL]`). Git authors: `joshboo1019-coder` = A (Task 2 commits),
`H-river` = B, `captol12` = C; "Initial commit: backbone skeleton" = the
group's shared backbone.

| Path | Owner | Student B (assist) changes — review status |
|---|---|---|
| `core/schema.py`, `core/interfaces.py`, `core/__init__.py` | ALL (backbone) | — |
| `core/config.py` | ALL (backbone) | `APPROACH_STOP_M(_BY_CLASS)` approach margin `[assist C]` — pending C + group |
| `main.py` | ALL (backbone) | `--mock`, `--scenario`, `E2E_TRACE_FILE` hook `[ALL]` — pending group |
| `assets/scenes/` (scene MJCF, meshes) | A | — |
| `skills/skills_real.py` | A (Task 2) | — |
| `skills/skills_mock.py`, `perception/perception_mock.py` | ALL (backbone mocks) | — |
| `dialogue/` (all modules) | B (Task 3 + bonuses: speech, VLM look, multi-goal, upgrades) | own work `[B]` |
| `perception/perception_real.py` | C (Task 4) | colour-grounding fix — reviewed by C |
| `perception/navigation.py` | C (Task 4) | stop margin; no ground truth in the range estimate (`assist/no-gt-height`) `[assist C]` — pending C |
| `perception/scenarios.py`, `perception/task4_cli.py` | C (Task 4) | — |
| `eval/*.py`, `eval/*.md`, `eval/results/`, `eval/run_env.sh` | B (Task 3 evaluation, prompts v1–v4, bonuses) | own work `[B]` |
| `eval/e2e/` (harness, drivers, `COMPARISON.md`, `S3_n3.md`) | B (shared e2e evidence) | own work `[B]`; `aggregate_s3.py` `[ALL]` |
| `tests/test_student_a.py` | A | — |
| `tests/test_student_b.py`, `test_bonus_b.py`, `test_upgrade_b.py` | B | own work `[B]` |
| `tests/test_student_c.py`, `test_task4_cli.py` | C | — |
| `tests/test_navigation_reacquire.py` | C | fixes `[assist C]` — pending C |
| `tests/test_c2_margin.py`, `test_color_grounding.py` | C | written by B `[assist C]` — pending C |
| `tests/test_architecture.py`, `test_handoff.py`, `test_task4_via_main.py`, `test_no_ground_truth.py` | ALL | handoff / task4-via-main by B — pending group |
| `tools/visual_test_*.py`, `capture_camera_evidence.py`, `fetch_scene_meshes.py`, `fit_mesh_scale.py`, `gen_task2_block_diagram.py` | A (`visual_test_task4.py` with C) | `visual_test_blue_chair_stairs.py`: no-GT range log `[assist C]` — pending C |
| `tools/task2_turn_trials.py`, `task2_turn_report.py`, `task2_render_evidence.py`, `docs/report_assets/task2/` | A (Task 2 evidence) | written by B `[assist A]` — pending A |
| `tools/task4_color_testset.py`, `c2_margin_analysis.py`, `docs/task4_*.md` | C (Task 4 evidence) | written by B `[assist C]` — pending C |
| `tools/check_status.py` | ALL (written by A) | — |
| `tools/make_submission_zip.sh`, `.env.example`, `docs/REPRODUCE.md` | ALL | by B — pending group |
| `docs/` (guides, `DECISIONS.md`, `TEAM_HANDOFF.md`) | ALL; `docs/test_result/` = A's camera evidence | — |

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
