"""Interactive Task 4 entry point with scenario and object-search prompts.

Run with ``python -m perception.task4_cli`` from the project root.
Or with ``MUJOCO_GL=egl python -m perception.task4_cli`` for browser view.

Choose one of the ten predefined layouts / robot start poses interactively,
or pass a scenario directly:
    python -m perception.task4_cli --list-scenarios
    python -m perception.task4_cli
    python -m perception.task4_cli --scenario 3
    python -m perception.task4_cli --scenario chairs_three_colors --debug-frames /tmp/dbg
"""

import argparse
import re
import tempfile
import time
from pathlib import Path
from typing import Optional

from core import config
from perception import scenarios


_SEARCH_ACTIONS = (
    r"go\s+(?:to|towards?)",
    r"move\s+(?:(?:over|closer)\s+)?(?:to|towards?|up\s+to)",
    r"approach",
    r"head\s+(?:over\s+)?(?:to|towards?)",
    r"navigate\s+(?:to|towards?)",
    r"travel\s+(?:to|towards?)",
    r"drive\s+(?:to|towards?)",
    r"walk\s+(?:to|towards?|up\s+to)",
    r"get\s+(?:to|towards?)",
    r"(?:go\s+and\s+)?find(?:\s+me)?",
    r"locate",
    r"search(?:\s+for)?",
    r"look\s+for",
)


def parse_search_command(text: str) -> Optional[dict[str, str]]:
    """Parse English search/approach phrasing into the Task 4 target JSON."""
    if not text.isascii():
        return None

    command = " ".join(text.strip().lower().split())
    command = re.sub(r"[.!?]+$", "", command).strip()
    if not command:
        return None

    actions = "|".join(sorted(_SEARCH_ACTIONS, key=len, reverse=True))
    request_prefix = (
        r"(?:(?:please|kindly)\s+|"
        r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)|"
        r"(?:i want you to\s+|i'd like you to\s+))?"
    )

    for target_key in config.OBJECT_POSITIONS:
        color, object_class = target_key.split("_", 1)
        target = rf"{re.escape(color)}\s+{re.escape(object_class)}"
        pattern = (
            rf"{request_prefix}(?:{actions})\s+"
            rf"(?:(?:the|a|an)\s+)?{target}"
        )
        if re.fullmatch(pattern, command):
            return {"class": object_class, "color": color}
    return None


def _read_scenario() -> scenarios.Scenario:
    scenarios.print_scenarios()
    while True:
        token = input("Choose a scenario (1-10 or name): ").strip().casefold()
        for scenario in scenarios.SCENARIOS:
            if token in (str(scenario.idx), scenario.name.casefold()):
                return scenario
        print("Invalid scenario. Enter a number from 1 to 10 or a scenario name.")


def _read_search_command() -> tuple[dict[str, str], str]:
    while True:
        text = input(
            "Task 4 object search in English "
            "(e.g. go to, approach, or move to the red stop sign): "
        )
        command = parse_search_command(text)
        if command is not None:
            return command, text.strip()
        print(
            "Command refused. Enter a search/approach command for a configured "
            "colored object."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task 4 object navigation.")
    parser.add_argument("--camera", default="dog_front_camera")
    parser.add_argument("--debug-frames", default=None, metavar="DIR")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--mock-perception", action="store_true")
    parser.add_argument("--scenario", default=None, metavar="N|NAME",
                        help="load one of the 10 predefined scenarios (1-10 or name): "
                             "its own objects + robot start pose")
    parser.add_argument("--list-scenarios", action="store_true",
                        help="print all scenarios and exit")
    parser.add_argument("--no-log", action="store_true",
                        help="don't append the result to docs/test_result/task4_trials.csv")
    args = parser.parse_args()

    if args.list_scenarios:
        scenarios.print_scenarios()
        return

    scenario = (
        scenarios.get_scenario(args.scenario)
        if args.scenario is not None
        else _read_scenario()
    )
    scenarios.apply_to_config(scenario)  # must happen BEFORE parsing the command
    scenarios.print_scenario(scenario)
    command, command_text = _read_search_command()

    # Keep robot/simulation imports below the validated command gate.
    from perception import navigation
    from skills.skills_real import RealSkills

    temp_root = Path(tempfile.gettempdir()).resolve()
    if temp_root == scenarios.PROJECT_ROOT or scenarios.PROJECT_ROOT in temp_root.parents:
        temp_root = scenarios.PROJECT_ROOT.parent

    with tempfile.TemporaryDirectory(
        prefix="task4_scenario_", dir=temp_root
    ) as temporary_directory:
        scene_path = scenarios.build_scene_xml(
            scenario, Path(temporary_directory)
        )
        print(f"[SCENARIO] temporary scene written to {scene_path}")

        print("Booting RealSkills...")
        skills = RealSkills(
            gui=not args.native,
            default_camera=args.camera,
            native_viewer=args.native,
            scene_path=str(scene_path),
        )
        try:
            time.sleep(1.0)
            scenarios.place_robot(skills, *scenario.robot)

            if args.mock_perception:
                from perception.perception_mock import MockPerception
                perception = MockPerception()
            else:
                from perception.perception_real import RealPerception
                perception = RealPerception(debug_dir=args.debug_frames)

            t0 = time.time()
            success = navigation.goto_object(
                command["class"], command["color"], skills, perception,
                command_text=command_text,
            )
            elapsed = time.time() - t0
            pose = skills.get_robot_pose()
            print(f"\ngoto_object returned success={success}")
            print("Robot final pose:", pose)

            if not args.no_log:
                scenarios.log_trial(scenario, command["class"], command["color"],
                                    success, pose, elapsed)
            print("Ctrl+C to exit.")
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            skills.shutdown()


if __name__ == "__main__":
    main()