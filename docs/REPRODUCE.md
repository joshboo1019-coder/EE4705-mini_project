<!-- Change contributed by Student B (assist), pending review by the group -->
# Fresh-clone reproducibility log

Run 2026-10-04 on Linux (Ubuntu, ROS Jazzy installed, 32 cores, no conda env
created), against `main` at `ee9593f`. Repo and
[quadruped_mujoco](https://github.com/aoqianz/quadruped_mujoco) (`dd40180`)
were cloned side by side into an empty directory. API keys exported in the
shell were removed for every run (`env -u DASHSCOPE_API_KEY -u GOOGLE_API_KEY
-u OPENAI_API_KEY`), and the repo-root `.env` held placeholders only
(`DASHSCOPE_API_KEY=placeholder`, etc.). No `--gui`, so port 8765 was never
bound.

## Setup

| Step | Command | Time |
|---|---|---|
| clone repo (37 MB) | `git clone -b main https://github.com/joshboo1019-coder/EE4705-mini_project.git` | 3 s |
| clone platform | `git clone https://github.com/aoqianz/quadruped_mujoco.git` (sibling) | 1 s |
| venv | `cd EE4705-mini_project && python3 -m venv .venv` (Python 3.13.5) | 1 s |
| platform | `env -u PYTHONPATH .venv/bin/pip install -e ../quadruped_mujoco` | 5 s |
| deps | `env -u PYTHONPATH .venv/bin/pip install -r requirements.txt` | 34 s (warm pip cache), `.venv` = 6.4 GB (CUDA torch via ultralytics) |
| placeholder keys | `printf 'DASHSCOPE_API_KEY=placeholder\n...' > .env` | — |

## Runs

| Check | Command | Result |
|---|---|---|
| test suite, as README said | `source .venv/bin/activate && python -m pytest -q tests/` | **fails at start**: ROS's `PYTHONPATH` loads the `launch_testing` pytest plugin → `No module named 'lark'` |
| test suite | `eval/run_env.sh -m pytest -q tests/` | 36 s wall (8.8 s in pytest): **95 passed, 6 failed**, then **segfault at interpreter exit (exit 139)** |
| A script | `eval/run_env.sh tests/test_student_a.py` | passes (0 s) |
| B script | `eval/run_env.sh tests/test_student_b.py` | live LLM: every line `[CMD] rejected reason=llm_error:AuthenticationError` (expected with placeholders), exit 0 |
| C script | `eval/run_env.sh tests/test_student_c.py` | **`Result: FAIL` (mission timeout) after 120 s and ~950 MB / 15.5 M lines of stdout** |
| architecture | `eval/run_env.sh -m pytest -q tests/test_architecture.py` | 3 passed |
| handoff | `eval/run_env.sh -m pytest -q tests/test_handoff.py` | 1 failed, 1 passed, 7 s (boots the real headless sim + YOLO) |
| mock pipeline | `printf 'turn left 90 degrees\nstop\n' \| timeout 60 eval/run_env.sh eval/mock_main.py` | chat loop up, both lines `rejected reason=llm_error:AuthenticationError`; does not exit on stdin EOF (ended by `timeout`) |
| real sim, no LLM | `printf 'p\nw\nw\nq\np\nquit\n' \| timeout 120 eval/run_env.sh -m skills.skills_real` | 2 s, exit 0: pose x 0.00 → 0.41 m, `[TURN] target=15.0 deg final_error=1.8 deg`, "Shut down cleanly." |
| real sim, turn test | `eval/run_env.sh -m skills.skills_real --compare-turn < /dev/null` | 5 s, exit 0: closed-loop error 2.0°, open-loop yaw 111.4° for a 90° target |
| full system | `(sleep 15; printf 'turn left 90 degrees\n'; sleep 20) \| timeout -s INT 45 eval/run_env.sh main.py` | sim + YOLO up in < 15 s, command `rejected reason=llm_error:AuthenticationError`, Ctrl+C exit |
| detector | `eval/run_env.sh -m perception.perception_real --image /tmp/frame.png` (copy of `docs/test_result/camera_evidence/20hz/frame_0119.png`) | 3 s, writes `/tmp/frame_detections.{jpg,json}` (`[]` on that frame) |

`yolo11n.pt` (5.6 MB) was downloaded into the repo root on the first
`RealPerception` (during `test_handoff`). Every real-sim run prints a
one-off `[CAMERA] render failed (EGL_BAD_ACCESS) ... recreate` line at boot and
EGL `Exception ignored in ... __del__` noise at exit; both are harmless.

A second clean clone that followed the **revised** README step by step
(`python3 -m venv .venv && source .venv/bin/activate && unset PYTHONPATH &&
pip install -e ../quadruped_mujoco && pip install -r requirements.txt`) took
51 s from `git clone` to installed (with a warm pip cache). In that clone,
`eval/run_env.sh -m pytest -q tests/test_student_b.py tests/test_architecture.py tests/test_bonus_b.py`
gave 69 passed, and the headless `skills.skills_real` run worked
(2 s, clean shutdown).

## Update for tag `final` (1b95477, 2026-10-04)

A fresh clone of tag `final` following README.md (grader test, 2026-10-04 14:40): install 46 s with a warm pip
cache (venv 6.4 GB incl. CUDA torch), `eval/run_env.sh -m pytest -q tests/` → **283 passed, 1 xfailed** (31 s, no
segfault: test_handoff no longer boots the sim), `main.py --mock` + "turn left 90 degrees" → `[CMD] actions=turn(90
deg) n=1` … `[DONE]`, headless `main.py --scenario 3` + "go to the green chair" → `[FOUND] … d=0.70 m`,
`[MISSION] status=SUCCESS`. The failures listed below were fixed on `chore/cli-tests` (merged); they describe the
state of `main` at ee9593f only.

## Known failures on `main` (ee9593f), for the owners to decide — historical, fixed since

- `test_handoff::test_main_wires_mocks_by_default` asserts
  `USE_REAL_SKILLS is False`, but `main.py` now ships with both real flags
  `True`. The other handoff test therefore boots the real sim and YOLO, and
  never shuts the sim down, which is the likely cause of the segfault at exit.
- `test_navigation_reacquire.py`, 5 tests: history length 8 vs. 20,
  steer-to-center tolerance, target projection (6.74 vs. 3.45 m), strafe
  `(0.4 m/s, 1.1 s)` vs. the test's `(0.6, 2.0)` (the `REACQUIRE_*` values in
  `core/config.py` were retuned), and `test_recenter_time_counts_toward_four_second_recovery`
  raises `UnboundLocalError` (`class _Skills(_Skills)` shadows the outer name).
- `tests/test_student_c.py` (script): MockPerception's fixed bounding box
  never reaches `FOUND_DISTANCE_M`, so the approach loops until the 120 s
  timeout while printing every step.

## README problems found → fixed in README.md

1. The repo itself was never cloned, and it was unclear where
   `quadruped_mujoco` should go. `eval/run_env.sh` needs it as a sibling (or
   `$QUADRUPED_MUJOCO_ROOT`). → Step 0 now clones both side by side.
2. Conda env vs. `eval/run_env.sh`: the script only runs `.venv/bin/python`.
   → Use a `python3 -m venv .venv`. Conda is still listed, with that caveat.
3. ROS `PYTHONPATH` breaks pytest and the venv. → `unset PYTHONPATH`, and all
   commands now go through `eval/run_env.sh`.
4. "`pip install -e .[dev]` works too" was wrong: the extras lack
   `python-dotenv` (needed once a `.env` exists) and `faster-whisper`. → The
   README now says to use `requirements.txt`. (Adding both to `pyproject.toml`
   is left to the group.)
5. API keys: the README only showed `export`. → It now documents the
   repo-root `.env`, the three key names, that the shell environment wins over
   `.env`, and what a missing key looks like.
6. YOLO weights were not mentioned. → They are auto-downloaded on first use
   into the repo root and git-ignored.
7. `tests/test_student_b.py` was described as mocked, but run as a script it
   calls the live LLM. `--image test_frame.png` pointed to a file that doesn't
   exist. There was no `--gui` or mock-pipeline command. → Fixed.
8. There was no way to build the submission zip.
   → Added `tools/make_submission_zip.sh`.
