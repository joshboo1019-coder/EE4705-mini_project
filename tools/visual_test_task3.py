# Owner: Student A (Task 2; visual check of Student B's Task 3)
"""
tools/visual_test_task3.py — WATCH Task 3 (Student B) run in the real sim.

Boots the REAL RealSkills (not the mock) and drives it through
dialogue/executor.py exactly the way main.py eventually will, so you can
watch a *parsed command batch* actually execute on the real robot.

Two paths, chosen automatically:
  1. If dialogue/llm_parser.py's _call_llm() is implemented, this script
     calls the REAL LLM parser on a sample English sentence and runs
     whatever it returns. This is the true end-to-end Task 3 check.
  2. If _call_llm() is still `raise NotImplementedError` (the current
     state as of writing this), it falls back to a fixed, hardcoded
     command batch instead. That still lets you watch the EXECUTOR wired
     to the REAL SKILLS work correctly — it just skips the LLM step,
     which is Student B's remaining TODO (see tools/check_status.py).

By default goto_object uses the MOCK perception (no YOLO/weights needed)
so this script runs with nothing but Task 2 finished; pass
--real-perception once perception/perception_real.py is ready to exercise
the full Task 2+3+4 chain together.

RUN (from the project root):
    python tools/visual_test_task3.py
    python tools/visual_test_task3.py --real-perception
    python tools/visual_test_task3.py --text "turn around and walk forward"
"""

import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.schema import CommandQueue, MoveCommand, TurnCommand
from dialogue.executor import CommandExecutor
from dialogue import llm_parser
from skills.skills_real import RealSkills

# Used only if the real LLM parser isn't wired up yet (_call_llm() stub).
FIXED_DEMO_COMMANDS = [
    MoveCommand(vx=0.6, vy=0.0, wz=0.0, duration=3.0),
    TurnCommand(angle_deg=180.0),
]


def try_real_llm(sample_text: str):
    """Returns a ParseResult, or None if _call_llm() is still a stub."""
    try:
        return llm_parser.parse_command(sample_text, history=[])
    except NotImplementedError:
        return None


def estimate_seconds(commands) -> float:
    """Rough runtime estimate so we know how long to wait before printing
    the final pose. Doesn't need to be exact -- just long enough."""
    total = 0.0
    for c in commands:
        if isinstance(c, MoveCommand):
            total += c.duration
        elif isinstance(c, TurnCommand):
            total += 5.0  # matches RealSkills.turn's own timeout floor
        else:
            total += 1.0
    return total + 2.0  # buffer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real-perception", action="store_true",
                     help="use perception.perception_real.RealPerception "
                          "for any goto_object commands (needs YOLO weights); "
                          "default is the mock, so this runs with only Task 2 done")
    ap.add_argument("--text", default="walk forward for three seconds, "
                                       "then turn left 180 degrees",
                     help="sample English sentence to send to the real LLM "
                          "parser, if it's implemented")
    ap.add_argument("--native", action="store_true",
                     help="open the native MuJoCo window instead of the "
                          "browser panel -- no keyboard is wired up here, "
                          "so the WSL2 on-keypress crash shouldn't trigger, "
                          "but it's unverified; fall back to the default "
                          "browser panel if it's unstable")
    args = ap.parse_args()

    print("Booting RealSkills (loads the ONNX policy + opens the MuJoCo scene)...")
    skills = RealSkills(gui=not args.native, native_viewer=args.native)
    time.sleep(1.0)

    if args.real_perception:
        from perception.perception_real import RealPerception
        perception = RealPerception()
    else:
        from perception.perception_mock import MockPerception
        perception = MockPerception()

    queue = CommandQueue()
    executor = CommandExecutor(skills, perception, queue)

    print(f"\nTrying the real LLM parser on: {args.text!r}")
    result = try_real_llm(args.text)

    if result is None:
        print("dialogue/llm_parser.py's _call_llm() is still a stub "
              "(raise NotImplementedError) -- falling back to a fixed, "
              "hardcoded command batch instead, so you can still watch "
              "the EXECUTOR + REAL SKILLS wiring work end-to-end. Once "
              "Student B implements _call_llm(), this script picks the "
              "real parser up automatically -- no changes needed here.")
        commands = FIXED_DEMO_COMMANDS
    elif not result.accepted:
        print(f"LLM parser rejected the sample text: {result.reject_reason}")
        return
    else:
        print(f"LLM parser accepted {len(result.commands)} action(s).")
        commands = result.commands

    queue.push_many(commands)

    # run_forever() blocks forever (it's meant to run on main.py's main
    # thread), so run it in a background thread here and just wait out a
    # time estimate instead of trying to "join" it.
    t = threading.Thread(target=executor.run_forever, daemon=True)
    t.start()

    wait_s = estimate_seconds(commands)
    print(f"Executing... (watch the browser panel; waiting ~{wait_s:.0f}s)")
    time.sleep(wait_s)

    print("\nDone. Robot final pose:", skills.get_robot_pose())
    print("Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        # See visual_test_task2.py's comment on this same spot: stop()
        # alone leaves the daemon sim thread (and, with --native, the
        # GLFW window) running, and tearing the process down around
        # them is what segfaults on exit. shutdown() joins the thread
        # and closes the native viewer first.
        print("\nShutting down...")
        skills.shutdown()


if __name__ == "__main__":
    main()
