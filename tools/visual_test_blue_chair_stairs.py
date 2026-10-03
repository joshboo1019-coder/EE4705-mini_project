"""
tools/visual_test_blue_chair_stairs.py -- detect blue_chair early (from the
base of the gentle staircase), track its estimated distance at each stage
of the climb, then do the final precise approach/stop once at the peak.

WHY THIS EXISTS:
`blue_chair` (core.config.OBJECT_POSITIONS["blue_chair"] = (3.45, 2.0)) sits
exactly on stairs_gentle's flat peak in both assets/scenes/custom_scene.xml
and custom_scene_meshes.xml (<body name="blue_chair" pos="3.45 2.0 0.4">,
z=0.4 = the peak box's top surface at z=0.375 + half the chair's own
seat thickness). It is not reachable by a flat-ground goto_object() call
the way the other five graded objects are -- the robot has to climb the
staircase first, and plain navigation.goto_object() calls
skills.move() internally (see its own _approach_step()), which has none of
climb_stairs()'s step-height/edge-drift handling -- running goto_object()
directly across the actual risers would be walking blind across terrain it
was never built to cross safely.

An earlier version of this script climbed all the way to the peak in one
climb_stairs() call, THEN ran goto_object() -- which works, but means the
robot never looks for or reports on blue_chair until after the climb is
already done. This version instead:

  1. Detects blue_chair BEFORE climbing at all, from the staircase's own
     approach point -- it's on top of a 0.375 m peak, so it's visible from
     a distance looking up the stairs, the same way a real quadruped would
     plan a route toward something it can already see.
  2. Climbs in short hops (climb_stairs() called repeatedly toward
     intermediate waypoints along the stairs_gentle strip, not one single
     call straight to the peak), checking for the chair and logging an
     estimated planar distance after each hop -- the same range-estimation
     math navigation.py already uses internally (_estimated_planar_distance/
     _estimated_target_position, imported directly rather than
     reimplemented), so these numbers are computed exactly the same way
     Task 4's own [RANGE] logging works everywhere else.
  3. Once at the peak, hands off to navigation.goto_object() for the final
     centered approach/stop/[FOUND] check -- the same state machine used
     for every other graded object, so the actual detection-to-stop
     behavior this is graded on still runs for real at the end, it just
     isn't the only point in the run where detection happens.

climb_stairs() itself is unchanged/untouched -- this only calls it more
than once, at shorter intervals, instead of once straight to the peak.
No obstacle avoidance here on purpose, same as before -- that's a separate
optional bonus feature, not part of this script.

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

from core import config
from perception import navigation
from skills.skills_real import RealSkills

# Same values as tools/visual_test_rough_terrain.py's FEATURES["stairs_gentle"]
# -- see that script's own module docstring/comments for how these were
# derived and real-run-verified (step geoms are 1.0 m half-width in y
# around the y=2.0 centerline; width_limit leaves a margin short of the
# physical edge so a drift-off-the-side is flagged before it actually
# happens).
STAIRS_GENTLE_APPROACH = (0.3, 2.0)
WIDTH_AXIS = "y"
WIDTH_CENTER = 2.0
WIDTH_LIMIT = 0.8

# Intermediate hops up the strip (x=[1.0, 5.9], peak at x=3.45), short
# enough that each climb_stairs() call covers a couple of risers at most --
# this is what makes "track distance while climbing" possible at all,
# since climb_stairs() itself is a single blocking call with no per-step
# callback. The last waypoint IS the peak, where blue_chair sits.
CLIMB_WAYPOINTS = [(1.5, 2.0), (2.5, 2.0), (3.45, 2.0)]


def _log_blue_chair_range(stage: str, skills, perception) -> None:
    """Grab one frame, look for blue_chair, print [DETECT]/[RANGE] lines
    using the exact same range-estimation helpers navigation.py's own
    goto_object() uses internally -- not a separate/different distance
    computation."""
    frame = skills.get_camera_frame()
    detections = perception.detect(frame)
    target = navigation._pick_target(detections, "chair", "blue")
    pose = skills.get_robot_pose()

    if target is None:
        print(f"[DETECT] stage={stage} blue_chair not visible this frame")
        return

    camera_height = navigation._camera_height_above_ground(skills)
    estimated = navigation._estimated_planar_distance(
        pose, target, frame.shape, camera_height
    )
    x_obj, y_obj = config.OBJECT_POSITIONS["blue_chair"]
    ground_truth = ((pose.x - x_obj) ** 2 + (pose.y - y_obj) ** 2) ** 0.5
    print(f"[DETECT] stage={stage} class={target.class_name} "
          f"color={target.color} conf={target.conf:.2f} "
          f"bbox={list(target.bbox)}")
    print(f"[RANGE] stage={stage} estimated_planar={estimated:.2f} m "
          f"ground_truth={ground_truth:.2f} m")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock-perception", action="store_true",
                     help="use perception.perception_mock.MockPerception "
                          "instead of real YOLO (logic-only check, no "
                          "camera/YOLO needed -- see visual_test_task4.py's "
                          "own caveat on this: it always 'finds' a fake "
                          "green chair after a few misses, so it can't "
                          "verify real detection of blue_chair specifically)")
    ap.add_argument("--camera", default="dog_front_camera",
                     help='camera selected on load: "dog_front_camera" '
                          '(default, robot POV -- what perception.detect() '
                          'actually sees), "tracking" (third-person), '
                          '"dog_rear_overhead_camera", or "dog_top_camera"')
    ap.add_argument("--debug-frames", metavar="DIR", default=None,
                     help="dump every camera frame + each detection's bbox "
                          "crop as PNGs into DIR during the final "
                          "goto_object() phase (same flag as "
                          "visual_test_task4.py)")
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

        if args.mock_perception:
            from perception.perception_mock import MockPerception
            print("Using MockPerception -- this checks the climb/approach "
                  "SEQUENCE only, not real detection or color grounding "
                  "(see visual_test_task4.py's own caveat).")
            perception = MockPerception()
        else:
            from perception.perception_real import RealPerception
            perception = RealPerception(debug_dir=args.debug_frames)
            if args.debug_frames:
                print(f"[DEBUG] saving frames + bbox crops to "
                      f"{args.debug_frames}/")

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

        # Detect BEFORE climbing at all -- blue_chair sits on a 0.375 m
        # peak, so it's plausibly visible looking up the stairs from here,
        # the same way a real search would spot a target before planning a
        # route to it.
        _log_blue_chair_range("before_climb", skills, perception)

        for waypoint in CLIMB_WAYPOINTS:
            print(f"\n>>> Climbing toward {waypoint}...")
            climb_outcome = skills.climb_stairs(
                *waypoint,
                width_axis=WIDTH_AXIS, width_center=WIDTH_CENTER,
                width_limit=WIDTH_LIMIT,
            )
            pose = skills.get_robot_pose()
            height = skills.get_trunk_height()
            print(f"    climb outcome={climb_outcome!r}  "
                  f"pose: x={pose.x:.2f} y={pose.y:.2f} "
                  f"yaw={pose.yaw_deg:.1f} trunk_z={height:.3f} m")
            if climb_outcome != "completed":
                print(f"[MISSION] status=FAIL reason=climb_{climb_outcome}")
                return
            _log_blue_chair_range(f"at_{waypoint}", skills, perception)

        print("\n>>> At the peak -- handing off to goto_object() for the "
              "final centered approach/stop...\n")
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
