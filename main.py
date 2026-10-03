"""
Change contributed by Student B (assist), pending review by the group:
--mock (chore/cli-tests), --scenario (assist/task4-via-main), the
E2E_TRACE_FILE hook (eval/e2e harness only), and --scene hard /
--gt-instance (assist/hard-scene, optional stress-test scene).

main.py — ALL. The only file that wires the real (or mock) implementations
together. Nobody develops against this file day-to-day; you only touch it
during integration, and each flag below can be flipped independently so
integration happens incrementally rather than all-at-once the night before
the deadline.
"""

import argparse
import os
import tempfile
import time
from pathlib import Path
from core.schema import CommandQueue
from dialogue.executor import CommandExecutor
from dialogue import chat_interface

# Flip these to False -> True one at a time as each student's real module
# becomes ready. Everything else in the codebase is unaffected by the flip.
USE_REAL_SKILLS = True
USE_REAL_PERCEPTION = True


def use_mocks():
    """`--mock`: wire MockSkills + MockPerception (no sim, no YOLO) for
    this run only, without editing the defaults above."""
    global USE_REAL_SKILLS, USE_REAL_PERCEPTION
    USE_REAL_SKILLS = USE_REAL_PERCEPTION = False


def build_skills(gui: bool = False, native: bool = False, scene_path=None):
    if USE_REAL_SKILLS:
        from skills.skills_real import RealSkills
        if scene_path is not None:
            return RealSkills(gui=gui, native_viewer=native, scene_path=str(scene_path))
        return RealSkills(gui=gui, native_viewer=native)
    from skills.skills_mock import MockSkills
    return MockSkills()


def build_perception():
    if USE_REAL_PERCEPTION:
        from perception.perception_real import RealPerception
        return RealPerception()
    from perception.perception_mock import MockPerception
    return MockPerception()


def load_scenario(token: str):
    """`--scenario N|NAME`: one of Student C's Task 4 layouts
    (perception/scenarios.py). Applies its object positions to config
    (ground truth stays logging-only) and writes its scene XML; returns
    (scenario, scene_path). The robot is placed after the sim boots."""
    from perception import scenarios
    scenario = scenarios.get_scenario(token)
    scenarios.apply_to_config(scenario)
    scenarios.print_scenario(scenario)
    if not USE_REAL_SKILLS:
        return scenario, None
    out = Path(tempfile.mkdtemp(prefix="minilab_scenario_"))
    scene_path = scenarios.build_scene_xml(scenario, out)
    print(f"[SCENARIO] temporary scene written to {scene_path}")
    return scenario, scene_path


def load_hard_scene(gt_instance=None):
    """`--scene hard`: the optional stress-test scene (perception/hard_scene.py,
    docs/hard_scene.md). Swaps config.OBJECT_POSITIONS for the hard scene's
    ground truth (logging only; "green_chair" -> green chair #1 unless
    --gt-instance picks #2) and returns the scene path (None with --mock).
    Dimmer lighting is applied after the sim boots (apply_lighting)."""
    from perception import hard_scene
    used = hard_scene.apply_to_config(gt_instance)
    hard_scene.print_layout(used)
    if not USE_REAL_SKILLS:
        return None
    return hard_scene.scene_path()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true",
                        help="browser control panel at http://localhost:8765 (real skills only)")
    parser.add_argument("--native", action="store_true",
                        help="native MuJoCo window (real skills only)")
    parser.add_argument("--mock", action="store_true", help="MockSkills + MockPerception (no sim, no YOLO)")
    parser.add_argument("--scenario", default=None, metavar="N|NAME", help="Task 4 layout + start pose from perception/scenarios.py (1-10 or name)")
    parser.add_argument("--scene", choices=("default", "hard"), default="default",
                        help="'hard': optional stress-test scene (assets/scenes/custom_scene_hard.xml: "
                             "2nd green chair, occluding walls, colour distractors, dim light); "
                             "mutually exclusive with --scenario")
    parser.add_argument("--gt-instance", default=None, metavar="KEY#N",
                        help="--scene hard only, logging only: which instance the [FOUND] d= / "
                             "[RANGE] ground_truth= logs measure to, e.g. 'green_chair#2'")
    args = parser.parse_args()
    if args.scene == "hard" and args.scenario is not None:
        parser.error("--scene hard and --scenario are mutually exclusive "
                     "(a scenario builds its own scene from the default one)")
    if args.gt_instance is not None and args.scene != "hard":
        parser.error("--gt-instance needs --scene hard")
    if args.mock:
        use_mocks()

    scenario, scene_path = (load_scenario(args.scenario)
                            if args.scenario is not None else (None, None))
    if args.scene == "hard":
        scene_path = load_hard_scene(args.gt_instance)
    skills = build_skills(gui=args.gui, native=args.native, scene_path=scene_path)
    if args.scene == "hard" and USE_REAL_SKILLS:
        from perception import hard_scene
        hard_scene.apply_lighting(skills)
    # e2e harness only (eval/e2e/trace.py): logs pose/tilt/contacts to a file
    # for evaluation when E2E_TRACE_FILE is set. Prints nothing, controls nothing.
    if os.environ.get("E2E_TRACE_FILE"):
        from eval.e2e.trace import start_trace
        start_trace(skills, os.environ["E2E_TRACE_FILE"])
    if scenario is not None and USE_REAL_SKILLS:
        from perception import scenarios
        time.sleep(1.0)          # let the sim thread start stepping
        scenarios.place_robot(skills, *scenario.robot)
    perception = build_perception()
    queue = CommandQueue()

    chat_interface.start_chat_thread(queue)

    executor = CommandExecutor(skills, perception, queue)
    executor.run_forever()  # blocks; keep the sim/physics alive in here
    # TODO(Student A): if your platform needs its own physics-stepping loop
    # driven from the main thread (rather than inside skills.move()), that
    # loop belongs here instead of a plain executor.run_forever() call —
    # discuss with B before changing this file.


if __name__ == "__main__":
    main()
