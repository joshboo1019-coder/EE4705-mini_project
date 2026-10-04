"""
eval/mock_main.py — STUDENT B OWNS THIS FILE. Task 3 smoke test.

Runs main.py's full pipeline (chat thread + executor) on
MockSkills / MockPerception without editing main.py's integration flags.
Thin wrapper around `main.py --mock` (any other CLI args are ignored).

    env -u PYTHONPATH .venv/bin/python eval/mock_main.py

--scenario (Task 3 upgrade): the same chat_interface + CommandExecutor, but
on eval/scenario_mock.py's KinematicSkills (moves follow the heading) and
ScenarioPerception (a fake camera on a toy world, so until_see can see
something), with a detection-only goto stub and a mock VLM. The parser is
the real one (config.LLM_SERVICE, one call per line). Commands are read
from stdin, one per line, each sent when the robot is idle; a line
"&<seconds> <text>" is sent <seconds> after the previous one WITHOUT
waiting, e.g. to stop a running program:

    printf '%s\\n' "walk in a square with 2 meter sides" "&1.0 stop" | \\
        eval/run_env.sh eval/mock_main.py --scenario
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402

main.USE_REAL_SKILLS = main.USE_REAL_PERCEPTION = False


def _idle(ex, queue) -> bool:
    return queue.empty() and not ex._busy


def _wait_idle(ex, queue) -> None:
    stable = 0
    while stable < 3:                # idle for 3 checks in a row (pop -> busy race)
        time.sleep(0.05)
        stable = stable + 1 if _idle(ex, queue) else 0


def run_scenario(lines, sleep_scale: float = 0.25) -> None:
    from core.schema import CommandQueue
    from dialogue import chat_interface
    from dialogue.executor import CommandExecutor
    from eval.scenario_mock import KinematicSkills, ScenarioPerception, mock_vlm, scenario_goto

    skills = KinematicSkills(sleep_scale=sleep_scale)
    perception = ScenarioPerception(skills)
    queue = CommandQueue()
    ex = CommandExecutor(skills, perception, queue, goto_object_fn=scenario_goto,
                         vlm_fn=mock_vlm, save_frame_fn=lambda frame: "(mock frame, not saved)")
    threading.Thread(target=ex.run_forever, kwargs={"poll_timeout": 0.05}, daemon=True).start()
    history = []
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("&"):
            delay, _, text = line[1:].partition(" ")
            time.sleep(float(delay))
        else:
            _wait_idle(ex, queue)
            text = line
        print(f"User: {text}", flush=True)
        chat_interface.handle_utterance(text, history, queue)
    _wait_idle(ex, queue)
    p = skills.get_robot_pose()
    print(f"[MOCK] final pose x={p.x:.2f} y={p.y:.2f} yaw={p.yaw_deg:.1f}")


if __name__ == "__main__":
    if "--scenario" in sys.argv[1:]:
        run_scenario(sys.stdin)
    else:
        sys.argv = sys.argv[:1] + ["--mock"]
        main.main()
