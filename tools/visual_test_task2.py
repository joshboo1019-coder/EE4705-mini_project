# Owner: Student A (Task 2)
"""
tools/visual_test_task2.py — WATCH Task 2 (Student A) run in the real sim.

This is the "see the robot move" check for Task 2: it boots the REAL
RealSkills (real MuJoCo physics + policy + camera), not the mock, and
drives it through a fixed choreography (forward, strafe, closed-loop
turns, stop) so you can watch it happen instead of typing keys yourself.

HOW TO WATCH IT:
  Defaults to gui=True, which opens RealSkills' browser control panel —
  that's what you should have open in a browser tab while this runs.
  This is the team's confirmed-working display path (see
  docs/DECISIONS.md / earlier WSLg troubleshooting notes).

  Pass --native to try the native MuJoCo window instead. It's been
  confirmed to run a full scripted sequence (walk/strafe/turn) cleanly;
  the one crash found was a "Segmentation fault (core dumped)" on exit,
  traced to skills.stop() (used in earlier versions of this script) not
  actually shutting the sim thread / GLFW window down before Python
  tore the process down around them. Fixed below by always calling
  skills.shutdown() in a `finally` block, so this should now exit
  cleanly on Ctrl+C. If you still see a crash, it's a new one — mention
  exactly when it happens.

RUN (from the project root):
    python tools/visual_test_task2.py
    python tools/visual_test_task2.py --native   # try the native window

This is also a good source clip for the handout's Video_Task2 — it's a
short, repeatable, unattended sequence rather than you live-typing keys.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.skills_real import RealSkills


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", action="store_true",
                     help="open the native MuJoCo window instead of the "
                          "browser panel (see module docstring)")
    args = ap.parse_args()

    print("Booting RealSkills (loads the ONNX policy + opens the MuJoCo scene)...")
    skills = RealSkills(gui=not args.native, native_viewer=args.native, default_camera="dog_front_camera")
    # Wrapped in try/finally, not just a KeyboardInterrupt handler: with
    # --native, RealSkills opens a real GLFW window and starts a daemon
    # thread that keeps calling into it. ANY unhandled exception past
    # this point (not just Ctrl+C) would otherwise let Python start
    # tearing the process down while that thread is still mid-flight
    # inside native GLFW/MuJoCo calls -- which segfaults on exit.
    # skills.shutdown() joins the thread and closes the native viewer
    # cleanly; putting it in `finally` guarantees it runs no matter how
    # this function exits.
    try:
        time.sleep(1.0)  # let the first frame/pose settle before moving

        steps = [
            ("Walk forward",       lambda: skills.move(vx=0.6, vy=0.0, wz=0.0, duration=2.0)),
            ("Strafe left",        lambda: skills.move(vx=0.0, vy=0.4, wz=0.0, duration=2.0)),
            ("Turn left 90 deg",   lambda: skills.turn(90.0)),
            ("Walk forward",       lambda: skills.move(vx=0.6, vy=0.0, wz=0.0, duration=2.0)),
            ("Turn right 180 deg", lambda: skills.turn(-180.0)),
            ("Walk forward",       lambda: skills.move(vx=0.6, vy=0.0, wz=0.0, duration=2.0)),
            ("Stand",              lambda: skills.stand()),
            ("Walk forward",       lambda: skills.move(vx=0.6, vy=0.0, wz=0.0, duration=2.0)),
            ("Turn right 90 deg",  lambda: skills.turn(-90)),
            ("Crouch",             lambda: skills.crouch()),
            ("Turn left 180 deg",  lambda: skills.turn(180)),
            ("Stop",               lambda: skills.stop()),
        ]

        for label, action in steps:
            pose_before = skills.get_robot_pose()
            print(f"\n>>> {label}  (pose before: x={pose_before.x:.2f} "
                  f"y={pose_before.y:.2f} yaw={pose_before.yaw_deg:.1f})")
            action()
            pose_after = skills.get_robot_pose()
            print(f"    pose after:  x={pose_after.x:.2f} y={pose_after.y:.2f} "
                  f"yaw={pose_after.yaw_deg:.1f}")

        print("\nDone. Robot final pose:", skills.get_robot_pose())
        print("Ctrl+C to exit (the sim keeps running otherwise).")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        skills.shutdown()


if __name__ == "__main__":
    main()
