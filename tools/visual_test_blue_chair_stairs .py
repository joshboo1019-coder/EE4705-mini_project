"""
tools/visual_test_blue_chair_stairs.py -- climb the gentle staircase, then
detect and approach the blue_chair sitting on its peak.

WHY THIS EXISTS:
`blue_chair` (core.config.OBJECT_POSITIONS["blue_chair"] = (3.45, 2.0)) sits
exactly on stairs_gentle's flat peak in both assets/scenes/custom_scene.xml
and custom_scene_meshes.xml (<body name="blue_chair" pos="3.45 2.0 0.4">,
z=0.4 = the peak box's top surface at z=0.375 + half the chair's own
0.05 m seat thickness). It is not reachable by a flat-ground goto_object()
call the way the other five graded objects are -- the robot has to climb
the staircase first. This script is the straight-line version of that:
climb to the peak, then run the same search/steer/approach/stop behavior
Task 4 already uses everywhere else, now pointed at an object that happens
to be elevated rather than on the ground. (tools/visual_test_rough_terrain.py
proves climb_stairs() itself works; this script is the first one to chain
it directly into navigation.goto_object() against a real target instead of
just walking to a bare coordinate and stopping.)

No obstacle avoidance here on purpose -- that's a separate, optional bonus
feature. This script only does the two things the handout's Task 4 grading
actually asks for: detect a graded object and navigate to it, with a
staircase crossing in between. If you also want the obstacle-avoidance
version, that's a different script with its own extra logic layered on top
of the same climb_stairs()+goto_object() combination used here.

SEQUENCE:
  1. cross_rough_terrain() to stairs_gentle's approach point (0.3, 2.0) --
     flat ground, no width guard needed (see visual_test_rough_terrain.py's
     own FEATURES["stairs_gentle"]["approach"], reused verbatim here).
  2. climb_stairs() all the way to the peak (3.45, 2.0) -- NOT stopping
     short the way a future obstacle-avoidance variant might, since there's
     nothing to avoid here and blue_chair itself is the destination.
     width_axis="y", width_center=2.0, width_limit=0.8 are the same
     real-run-tuned values visual_test_rough_terrain.py already verified
     for this staircase's strip.
  3. navigation.goto_object("chair", "blue", skills, perception) -- the
     same Task 4 search/steer/approach/stop state machine used for every
     other object, run from wherever the climb left the robot (right at
     the peak, a few meters from the chair instead of starting from
     spawn), so [SEARCH]/[DETECT]/[FOUND]/[MISSION] all print exactly as
     they do in tools/visual_test_task4.py.

If the climb doesn't report "completed" (edge_drift/stuck/incomplete),
this script stops and reports that instead of attempting goto_object() from
an unreliable position -- same reasoning as
tools/visual_test_rough_terrain.py's own run_feature() (approaching a
detection from a stuck/tipped state would misreport a navigation failure
as if it were a detection failure).

RUN (from the project root):
    python tools/visual_test_blue_chair_stairs.py
    python tools/visual_test_blue_chair_stairs.py --mock-perception
    python tools/visual_test_blue_chair_stairs.py --debug-frames /tmp/blue_chair_dbg
    python tools/visual_test_blue_chair_stairs.py --native
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from perception import navigation
from skills.skills_real import RealSkills

# Same values as tools/visual_test_rough_terrain.py's FEATURES["stairs_gentle"]
# -- see that script's own module docstring/comments for how these were
# derived and real-run-verified (step geoms are 1.0 m half-width in y
# around the y=2.0 centerline; width_limit leaves a margin short of the
# physical edge so a drift-off-the-side is flagged before it actually
# happens).
STAIRS_GENTLE_APPROACH = (0.3, 2.0)
STAIRS_GENTLE_PEAK = (3.45, 2.0)   # blue_chair sits right here, z=0.4
WIDTH_AXIS = "y"
WIDTH_CENTER = 2.0
WIDTH_LIMIT = 0.8


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock-perception", action="store_true",
                     help="use perception.perception_mock.MockPerception "
                          "instead of real YOLO (navigation state-machine "
                          "check only, no camera/YOLO needed -- see "
                          "tools/visual_test_task4.py's own caveat on this)")
    ap.add_argument("--camera", default="dog_front_camera",
                     help='camera selected on load: "dog_front_camera" '
                          '(default, robot POV -- what perception.detect() '
                          'actually sees), "tracking" (third-person), '
                          '"dog_rear_overhead_camera", or "dog_top_camera"')
    ap.add_argument("--debug-frames", metavar="DIR", default=None,
                     help="dump every camera frame + each detection's bbox "
                          "crop as PNGs into DIR during the goto_object() "
                          "phase (same flag as visual_test_task4.py)")
    ap.add_argument("--native", action="store_true",
                     help="open the native MuJoCo window instead of the "
                          "browser panel (see visual_test_task4.py's own "
                          "--native caveat: the offscreen renderer feeding "
                          "get_camera_frame() can silently stall under "
                          "--native -- prefer the browser panel for this "
                          "script too, same reason)")
    args = ap.parse_args()

    print("Booting RealSkills (loads the ONNX policy + opens the MuJoCo scene)...")
    skills = RealSkills(gui=not args.native, default_camera=args.camera,
                         native_viewer=args.native)
    try:
        time.sleep(1.0)

        print(f"\n>>> Walking to stairs_gentle's approach point "
              f"{STAIRS_GENTLE_APPROACH}...")
        approach_outcome = skills.cross_rough_terrain(
            *STAIRS_GENTLE_APPROACH, segment_len=0.5
        )
        pose = skills.get_robot_pose()
        print(f"    approach outcome={approach_outcome!r}  "
              f"pose: x={pose.x:.2f} y={pose.y:.2f} yaw={pose.yaw_deg:.1f}")
        if approach_outcome != "completed":
            print(f"[MISSION] status=FAIL reason=approach_{approach_outcome}")
            return

        print(f"\n>>> Climbing stairs_gentle to its peak "
              f"{STAIRS_GENTLE_PEAK} (blue_chair sits right here)...")
        climb_outcome = skills.climb_stairs(
            *STAIRS_GENTLE_PEAK,
            width_axis=WIDTH_AXIS, width_center=WIDTH_CENTER,
            width_limit=WIDTH_LIMIT,
        )
        pose = skills.get_robot_pose()
        height = skills.get_trunk_height()
        print(f"    climb outcome={climb_outcome!r}  "
              f"pose: x={pose.x:.2f} y={pose.y:.2f} yaw={pose.yaw_deg:.1f} "
              f"trunk_z={height:.3f} m")
        if climb_outcome != "completed":
            print(f"[MISSION] status=FAIL reason=climb_{climb_outcome}")
            return

        if args.mock_perception:
            from perception.perception_mock import MockPerception
            print("\nUsing MockPerception -- this checks goto_object()'s "
                  "search/steer/approach STATE MACHINE only, not real "
                  "detection or color grounding (see "
                  "visual_test_task4.py's own caveat).")
            perception = MockPerception()
        else:
            from perception.perception_real import RealPerception
            perception = RealPerception(debug_dir=args.debug_frames)
            if args.debug_frames:
                print(f"[DEBUG] saving frames + bbox crops to "
                      f"{args.debug_frames}/")

        print("\n>>> goto_object(class='chair', color='blue') from the "
              "staircase peak...\n")
        success = navigation.goto_object("chair", "blue", skills, perception)

        print(f"\ngoto_object returned success={success}")
        print("Robot final pose:", skills.get_robot_pose())
        print("Ctrl+C to exit (the sim keeps running otherwise).")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        skills.shutdown()


if __name__ == "__main__":
    main()
