"""Interactive Task 4 entry point with a pre-start object-search prompt.

Run with ``python -m perception.task4_cli`` from the project root.
"""

import argparse
import json
import re
import time
from typing import Optional

from core import config


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
    args = parser.parse_args()

    command = _read_search_command()

    # Keep robot/simulation imports below the validated command gate.
    from perception import navigation
    from skills.skills_real import RealSkills

    print("Booting RealSkills...")
    skills = RealSkills(
        gui=not args.native,
        default_camera=args.camera,
        native_viewer=args.native,
    )
    try:
        time.sleep(1.0)
        if args.mock_perception:
            from perception.perception_mock import MockPerception
            perception = MockPerception()
        else:
            from perception.perception_real import RealPerception
            perception = RealPerception(debug_dir=args.debug_frames)

        success = navigation.goto_object(
            command["class"], command["color"], skills, perception
        )
        print(f"\ngoto_object returned success={success}")
        print("Robot final pose:", skills.get_robot_pose())
        print("Ctrl+C to exit.")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        skills.shutdown()


if __name__ == "__main__":
    main()