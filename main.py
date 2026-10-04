# Owner: ALL (backbone)
"""
Change contributed by Student B (assist), pending review by the group:
--mock (chore/cli-tests), --scenario (assist/task4-via-main), and the
E2E_TRACE_FILE hook (eval/e2e harness only).

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


def _wait_until_sim_ready(skills, timeout_s: float = 15.0, min_wall_s: float = 2.0) -> None:
    """Before teleporting the robot for a --scenario: wait until the sim thread
    is stepping and the onboard camera delivers frames, instead of a fixed
    1.0 s. Two e2e launches hung inside place_robot right after the camera's
    EGL renderer re-creation on the sim thread ("never became ready")."""
    t0 = time.time()
    sim_time = getattr(skills, "_get_sim_time", None)
    start = sim_time() if sim_time else 0.0
    while time.time() - t0 < timeout_s:
        stepping = sim_time is None or sim_time() - start >= 0.5
        if stepping and time.time() - t0 >= min_wall_s and skills.get_camera_frame() is not None:
            break
        time.sleep(0.1)
    print(f"[SCENARIO] sim ready after {time.time() - t0:.1f} s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true",
                        help="browser control panel at http://localhost:8765 (real skills only)")
    parser.add_argument("--native", action="store_true",
                        help="native MuJoCo window (real skills only)")
    parser.add_argument("--mock", action="store_true", help="MockSkills + MockPerception (no sim, no YOLO)")
    parser.add_argument("--scenario", default=None, metavar="N|NAME", help="Task 4 layout + start pose from perception/scenarios.py (1-10 or name)")
    args = parser.parse_args()
    if args.mock:
        use_mocks()

    scenario, scene_path = (load_scenario(args.scenario)
                            if args.scenario is not None else (None, None))
    skills = build_skills(gui=args.gui, native=args.native, scene_path=scene_path)
    # e2e harness only (eval/e2e/trace.py): logs pose/tilt/contacts to a file
    # for evaluation when E2E_TRACE_FILE is set. Prints nothing, controls nothing.
    if os.environ.get("E2E_TRACE_FILE"):
        from eval.e2e.trace import start_trace
        start_trace(skills, os.environ["E2E_TRACE_FILE"])
    if scenario is not None and USE_REAL_SKILLS:
        from perception import scenarios
        _wait_until_sim_ready(skills)
        scenarios.place_robot(skills, *scenario.robot)
    perception = build_perception()
    queue = CommandQueue()

    chat_interface.start_chat_thread(queue)

    executor = CommandExecutor(skills, perception, queue)
    executor.run_forever()  # blocks; keep the sim/physics alive in here
    # run_forever returns only after EOF on stdin (Ctrl+D / end of piped input)
    shutdown = getattr(skills, "shutdown", None)
    if callable(shutdown):
        shutdown()
    # TODO(Student A): if your platform needs its own physics-stepping loop
    # driven from the main thread (rather than inside skills.move()), that
    # loop belongs here instead of a plain executor.run_forever() call —
    # discuss with B before changing this file.


if __name__ == "__main__":
    main()
