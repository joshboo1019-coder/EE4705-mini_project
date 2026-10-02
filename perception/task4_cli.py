"""Interactive Task 4 entry point with a pre-start object-search prompt.

Run with ``python -m perception.task4_cli`` from the project root.

Scenario mode (10 predefined layouts / robot start poses):
    python -m perception.task4_cli --list-scenarios
    python -m perception.task4_cli --scenario 3
    python -m perception.task4_cli --scenario chairs_three_colors --debug-frames /tmp/dbg
"""

import argparse
import json
import re
import time
from typing import Optional

from core import config
from perception import scenarios


def parse_search_command(text: str) -> Optional[dict[str, str]]:
    """Parse supported English object-search commands into Task 4 JSON."""
    if not text.isascii():
        return None

    command = " ".join(text.strip().lower().rstrip(".!?").split())
    if not command:
        return None

    for target_key in config.OBJECT_POSITIONS:
        color, object_class = target_key.split("_", 1)
        target = rf"{re.escape(color)}\s+{re.escape(object_class)}"
        pattern = (
            rf"(?:go to|find|locate|search for)\s+"
            rf"(?:(?:the|a|an)\s+)?{target}"
        )
        if re.fullmatch(pattern, command):
            return {"class": object_class, "color": color}
    return None


def _read_search_command() -> dict[str, str]:
    while True:
        text = input("Task 4 object search in English (e.g. go to the red stop sign): ")
        command = parse_search_command(text)
        if command is not None:
            print(json.dumps(command))
            return command
        print("Command refused. Enter an English search for a configured colored object.")


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

    scenario = None
    scene_path = None
    if args.scenario is not None:
        scenario = scenarios.get_scenario(args.scenario)
        scene_path = scenarios.build_scene_xml(scenario)
        scenarios.apply_to_config(scenario)  # must happen BEFORE the command prompt
        scenarios.print_scenario(scenario)
        print(f"[SCENARIO] scene written to {scene_path}")

    command = _read_search_command()

    # Keep robot/simulation imports below the validated command gate.
    from perception import navigation
    from skills.skills_real import RealSkills

    print("Booting RealSkills...")
    skills_kwargs = dict(
        gui=not args.native,
        default_camera=args.camera,
        native_viewer=args.native,
    )
    if scene_path is not None:
        skills_kwargs["scene_path"] = str(scene_path)
    skills = RealSkills(**skills_kwargs)
    try:
        time.sleep(1.0)
        if scenario is not None:
            scenarios.place_robot(skills, *scenario.robot)

        if args.mock_perception:
            from perception.perception_mock import MockPerception
            perception = MockPerception()
        else:
            from perception.perception_real import RealPerception
            perception = RealPerception(debug_dir=args.debug_frames)

        t0 = time.time()
        success = navigation.goto_object(
            command["class"], command["color"], skills, perception
        )
        elapsed = time.time() - t0
        pose = skills.get_robot_pose()
        print(f"\ngoto_object returned success={success}")
        print("Robot final pose:", pose)

        if scenario is not None and not args.no_log:
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