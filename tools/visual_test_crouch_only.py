"""
tools/visual_test_crouch_only.py — isolate WHEN crouch() can work.

WHY THIS EXISTS (updated after real runs -- see docs/DECISIONS.md):
`tools/visual_test_task2.py`'s full choreography does Stand -> Walk ->
Turn -> Crouch -> Turn -> Stand, and a real run showed trunk_z stuck at
~0.33 m through the whole sequence -- neither Crouch nor the second Stand
visibly moved it, even with skills.set_height()'s per-step ramp (see
skills_real.py). Two earlier runs of THIS script narrowed down why:

  Run 1 -- crouch() called with NOTHING before it (straight after boot,
  no move()/turn()/stand()): trunk_z was already at the ~0.33 m standing
  equilibrium before the command, and crouch()'s ramp never moved it at
  all. Conclusion at the time: height_cmd does nothing while idle.

  Run 2 (this version) -- crouch() called right after a 2s move(vx=0.6)
  + a 1s pause: the FIRST [HEIGHT] step line hit the 0.28 m target
  exactly, but by the end of the same call's settle_s hold, trunk_z had
  drifted back UP to 0.33 m on its own -- with height_cmd still
  commanding 0.28 m the whole time.

  Conclusion: height_cmd is NOT simply ignored. It is tracked
  transiently, immediately after/during LINEAR motion (vx/vy nonzero),
  and gets overridden by a separate learned standing-balance behavior
  as soon as the robot is idle for long enough -- independent of what
  height_cmd is still asking for. This also explains the stuck-at-0.33
  task2 result: Crouch there is preceded by "Turn right 90", which is
  wz-only (vx=vy=0) -- the same "no linear motion" state as Run 1, not
  the "just walked" state that produced the transient dip here. Turning
  in place does not appear to trigger the same transient tracking that
  forward/lateral walking does.

This script now deliberately walks (skills.move(vx=0.6, ...)) right
before crouch() to reproduce the transient-tracking window, instead of
calling crouch() cold. Watch for exactly this pattern in the output:
the first [HEIGHT] step line reaching ~0.28 m, followed by the final
trunk_z_after line having drifted back up toward ~0.33 m despite no new
command -- that drift IS the standing-balance override, caught in the
act within a single crouch() call.

RUN (from the project root):
    python tools/visual_test_crouch_only.py
    python tools/visual_test_crouch_only.py --native

Reads the same [HEIGHT] step lines set_height() already prints -- no new
logging added here beyond one extra trunk_z readout right after the walk
(see below), so the transient-dip-then-drift-back pattern is visible
without digging through skills_real.py's internals.
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

        # Read trunk_z BEFORE ever touching height_cmd, straight after the
        # post-reset settle. This is the key new data point: if this is
        # already close to what set_height()'s first [HEIGHT] step later
        # reports (rather than close to the 0.25 m height_cmd default),
        # it means the robot settles to that height on its own -- e.g. as
        # part of ordinary standing-still balance behavior -- and
        # height_cmd was never really driving it there to begin with.
        z_at_boot = skills.get_trunk_height()
        print(f"\n[DIAGNOSTIC] trunk_z immediately after boot settle, "
              f"before any height command = {z_at_boot:.3f} m "
              f"(height_cmd default is 0.25 m -- compare these)")

        pose_before = skills.get_robot_pose()
        print(f"\n>>> Walking forward first (vx=0.6, 2.0s), THEN Crouch --"
              f" this is the setup that reproduces transient height_cmd "
              f"tracking (see module docstring)  (pose before: "
              f"x={pose_before.x:.2f} y={pose_before.y:.2f} "
              f"yaw={pose_before.yaw_deg:.1f})")

        skills.move(vx=0.6, vy=0.0, wz=0.0, duration=2.0)
        time.sleep(1.0)  # real-time pause; sim physics keep stepping in the
                          # background thread throughout (see move()'s own
                          # docstring), so this is "idle time after walking",
                          # not a pause in simulated time.

        z_after_walk = skills.get_trunk_height()
        print(f"[DIAGNOSTIC] trunk_z right after the walk, still before "
              f"crouch()'s height command = {z_after_walk:.3f} m -- compare "
              f"this against crouch()'s own trunk_z_before line below (if "
              f"they roughly match, the gap already closed during the 1s "
              f"pause above, before crouch() even started ramping).")

        skills.crouch()
        pose_after = skills.get_robot_pose()
        print(f"    pose after:  x={pose_after.x:.2f} y={pose_after.y:.2f} "
              f"yaw={pose_after.yaw_deg:.1f}")

        print(
            f"\nWhat to look for (see module docstring for the full "
            f"explanation):\n"
            f"  [DIAGNOSTIC] trunk_z at boot (idle, no command yet)  "
            f"= {z_at_boot:.3f} m\n"
            f"  [DIAGNOSTIC] trunk_z right after the walk (idle again, "
            f"before crouch's ramp) = {z_after_walk:.3f} m\n"
            "  - crouch()'s own [HEIGHT] step line, printed above, should "
            "hit ~0.28 m right as the ramp finishes -- that's height_cmd "
            "being tracked WHILE the robot still has recent linear-motion "
            "state (vx was just nonzero). This is the thing Run 1 (no "
            "move() before crouch()) never showed at all.\n"
            "  - crouch()'s final trunk_z_after line, also printed above, "
            "should then have drifted back UP toward ~0.33 m by the end "
            "of the settle_s hold, even though height_cmd never changed "
            "from 0.28 m -- that's the standing-balance behavior "
            "overriding the command once the robot has been idle long "
            "enough, caught mid-drift in a single call.\n"
            "  - If instead trunk_z_after also sits near 0.28 m (no "
            "drift-back), that would mean the override needs more idle "
            "time than this run gave it -- worth re-testing with a longer "
            "settle_s before concluding the pattern above doesn't hold."
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
