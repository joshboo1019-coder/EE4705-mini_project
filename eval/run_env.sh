#!/usr/bin/env bash
# Owner: Student B (shared run wrapper, used by ALL)
# eval/run_env.sh — run a project Python command on the real platform.
#
#   eval/run_env.sh main.py --gui                    # demo: browser panel at http://localhost:8765
#   eval/run_env.sh -m skills.skills_real --compare-turn
#   eval/run_env.sh -m pytest -q tests/
#
# Drops ROS's PYTHONPATH (it breaks the venv), points QUADRUPED_MUJOCO_ROOT at
# the sibling clone (override by exporting it first), and runs from the repo
# root with the project .venv. No API keys here: llm_parser reads them from
# the environment or the git-ignored repo-root .env.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export QUADRUPED_MUJOCO_ROOT="${QUADRUPED_MUJOCO_ROOT:-$(dirname "$REPO")/quadruped_mujoco}"
unset PYTHONPATH

# The robot's offscreen camera renders on the sim thread. Under the default
# GLFW/GLX backend that context can't be made current there, so frames come
# back black; EGL recovers after one retry. The native viewer needs GLFW.
if [[ " $* " != *" --native "* ]]; then
    export MUJOCO_GL="${MUJOCO_GL:-egl}"
fi

# --mock (MockSkills + MockPerception) never imports the platform.
if [[ " $* " != *" --mock "* && ! -f "$QUADRUPED_MUJOCO_ROOT/eg/play.py" ]]; then
    echo "quadruped_mujoco not found at $QUADRUPED_MUJOCO_ROOT" >&2
    echo "clone it: git clone https://github.com/aoqianz/quadruped_mujoco \"$QUADRUPED_MUJOCO_ROOT\"" >&2
    exit 1
fi

cd "$REPO"
exec "$REPO/.venv/bin/python" -u "$@"
