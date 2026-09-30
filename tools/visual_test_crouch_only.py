"""
tools/visual_test_crouch_only.py — isolate whether crouch() can work at all.

WHY THIS EXISTS:
`tools/visual_test_task2.py`'s full choreography does Stand -> Turn ->
Crouch -> Turn -> Stand, and a real run showed the robot's trunk_z getting
stuck at ~0.33 m from the first Stand onward -- neither the later Crouch
(target 0.20 m) nor the second Stand (target 0.35 m) moved trunk_z at all,
even with skills.set_height()'s per-step ramp (see skills_real.py). That
result doesn't distinguish two different explanations:

  (a) The policy just can't track height_cmd well once the robot has
      already been displaced away from its default 0.25 m stance (i.e.
      only the FIRST height change after boot works at all, regardless
      of which direction it is), possibly compounded by residual
      tilt/velocity left over from the move()/turn() calls in between; or
  (b) crouch() (lowering) specifically doesn't work, even as the very
      first height command straight from the 0.25 m default -- which
      would point at something direction-specific (e.g. gravity/loading
      making a downward stance harder for this policy), not just "stuck
      after one change".

This script calls ONLY skills.crouch() -- no move(), no turn(), no
stand() first -- immediately after boot, so the very first height
command the robot ever receives is a downward one from the untouched
0.25 m default. If trunk_z genuinely descends toward 0.20 m here, that
rules out (b) and points at (a) instead (something about the sequence,
not crouch() itself). If it still doesn't move, that's evidence for (b)
or a more basic policy/height_cmd limitation, independent of any
prior move()/turn() calls.

RUN (from the project root):
    python tools/visual_test_crouch_only.py
    python tools/visual_test_crouch_only.py --native

Reads the same [HEIGHT] step lines set_height() already prints -- no new
logging added here, this script just controls what happens before the
first height command so those lines are easier to interpret in isolation.
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
                          "browser panel (see tools/visual_test_task2.py's "
                          "docstring for the current --native caveats)")
    args = ap.parse_args()

    print("Booting RealSkills (loads the ONNX policy + opens the MuJoCo scene)...")
    skills = RealSkills(gui=not args.native, native_viewer=args.native)
    try:
        time.sleep(1.0)  # let the first frame/pose settle before touching height

        pose_before = skills.get_robot_pose()
        print(f"\n>>> Crouch (first height command since boot, no move()/turn() "
              f"before it)  (pose before: x={pose_before.x:.2f} "
              f"y={pose_before.y:.2f} yaw={pose_before.yaw_deg:.1f})")
        skills.crouch()
        pose_after = skills.get_robot_pose()
        print(f"    pose after:  x={pose_after.x:.2f} y={pose_after.y:.2f} "
              f"yaw={pose_after.yaw_deg:.1f}")

        print(
            "\nRead the [HEIGHT] step lines above: if trunk_z genuinely "
            "trends down toward 0.20 m here (even if it doesn't fully "
            "reach it), crouch() itself works, and the earlier stuck-at-"
            "0.33 result was caused by something in the "
            "Stand->Turn->Crouch sequence, not by crouch()'s own logic. "
            "If trunk_z stays flat here too, that's evidence crouch() / "
            "downward height_cmd doesn't track even as the very first "
            "height command from the 0.25 m default."
        )

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
