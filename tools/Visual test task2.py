"""
tools/visual_test_task2.py — WATCH Task 2 (Student A) run in the real sim.

This is the "see the robot move" check for Task 2: it boots the REAL
RealSkills (real MuJoCo physics + policy + camera), not the mock, and
drives it through a fixed choreography (forward, strafe, closed-loop
turns, stop) so you can watch it happen instead of typing keys yourself.

HOW TO WATCH IT:
  Native MuJoCo viewer under WSL2 is unreliable (see docs/DECISIONS.md /
  your own troubleshooting notes on WSLg), so this defaults to gui=True,
  which opens RealSkills' browser control panel — that's what you should
  have open in a browser tab while this runs.

RUN (from the project root):
    python tools/visual_test_task2.py

This is also a good source clip for the handout's Video_Task2 — it's a
short, repeatable, unattended sequence rather than you live-typing keys.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.skills_real import RealSkills


def main():
    print("Booting RealSkills (loads the ONNX policy + opens the MuJoCo scene)...")
    skills = RealSkills(gui=True)
    time.sleep(1.0)  # let the first frame/pose settle before moving

    steps = [
        ("Walk forward",       lambda: skills.move(vx=0.6, vy=0.0, wz=0.0, duration=3.0)),
        ("Strafe left",        lambda: skills.move(vx=0.0, vy=0.4, wz=0.0, duration=2.0)),
        ("Turn left 90 deg",   lambda: skills.turn(90.0)),
        ("Walk forward",       lambda: skills.move(vx=0.6, vy=0.0, wz=0.0, duration=2.0)),
        ("Turn right 180 deg", lambda: skills.turn(-180.0)),
        ("Walk forward",       lambda: skills.move(vx=0.6, vy=0.0, wz=0.0, duration=2.0)),
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
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        skills.stop()


if __name__ == "__main__":
    main()
