# Owner: Student B (Task 3 + bonuses)
"""
eval/e2e/drivers/scenario_main.py — Student B. BASELINE-only S3 driver.

main.py with one of Student C's perception/scenarios.py layouts, for the
baseline e2e run before main.py itself had --scenario (assist/task4-via-main):

    eval/run_env.sh eval/e2e/drivers/scenario_main.py --scenario N [--gui]

It uses only the mechanism scenarios.py offers (build_scene_xml,
apply_to_config, place_robot, exactly like perception/task4_cli.py), then runs
main.py's own pipeline unchanged: chat thread -> llm_parser.parse_command ->
CommandExecutor -> navigation.goto_object.
"""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
from core.schema import CommandQueue  # noqa: E402
from dialogue import chat_interface  # noqa: E402
from dialogue.executor import CommandExecutor  # noqa: E402
from perception import scenarios  # noqa: E402


def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--gui", action="store_true")
    args = ap.parse_args()

    s = scenarios.get_scenario(args.scenario)
    scenarios.apply_to_config(s)
    scenarios.print_scenario(s)
    out = Path(tempfile.mkdtemp(prefix="e2e_scenario_", dir="/tmp"))
    scene = scenarios.build_scene_xml(s, out)

    from skills.skills_real import RealSkills
    skills = RealSkills(gui=args.gui, scene_path=str(scene))
    if os.environ.get("E2E_TRACE_FILE"):
        from eval.e2e.trace import start_trace
        start_trace(skills, os.environ["E2E_TRACE_FILE"])
    time.sleep(1.0)
    scenarios.place_robot(skills, *s.robot)

    perception = main.build_perception()
    queue = CommandQueue()
    chat_interface.start_chat_thread(queue)
    CommandExecutor(skills, perception, queue).run_forever()


if __name__ == "__main__":
    run()
