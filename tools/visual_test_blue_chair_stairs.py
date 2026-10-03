"""
tools/visual_test_blue_chair_stairs.py -- detect blue_chair from the base of
the gentle staircase, climb to just short of it, then do the final precise
approach/stop.

WHY THIS EXISTS:
`blue_chair` (core.config.OBJECT_POSITIONS["blue_chair"] = (3.45, 2.0)) sits
exactly on stairs_gentle's flat peak in both assets/scenes/custom_scene.xml
and custom_scene_meshes.xml (<body name="blue_chair" pos="3.45 2.0 0.4">,
z=0.4 = the peak box's top surface at z=0.375 + half the chair's own seat
thickness). It is not reachable by a flat-ground goto_object() call the way
the other five graded objects are -- the robot has to climb the staircase
first, and plain navigation.goto_object() calls skills.move() internally
(see its own _approach_step()), which has none of climb_stairs()'s
step-height/edge-drift handling -- running goto_object() directly across
the actual risers would be walking blind across terrain it was never built
to cross safely.

SEQUENCE:
  1. Walk to stairs_gentle's approach point (0.3, 2.0) -- flat ground, no
     width guard needed (cross_rough_terrain()).
  2. Detect blue_chair RIGHT HERE, at the base, before any climbing starts
     -- it's on top of a 0.375 m peak, so it's plausibly visible looking
     up the stairs from the approach point, the same way a real search
     would spot a target before planning a route to it. This is the ONLY
     detection point before the final approach -- an earlier version of
     this script also re-checked partway up the staircase, but a real run
     showed that produces unreliable results (a spurious "airplane"
     misdetection from the odd elevated viewing angle mid-climb), and
     mid-climb detections were never acted on anyway (climb_stairs()
     itself has no per-step callback to redirect based on them), so
     there's no actual benefit to checking there -- only noise.
  3. Climb in ONE climb_stairs() call to (2.9, 2.0), NOT blue_chair's own
     (3.45, 2.0) -- see CLIMB_TARGET's own comment below for why a real
     run climbing straight to the chair's exact coordinates got the robot
     physically wedged against its collision geometry.
  4. From just short of the chair, hand off to navigation.goto_object() for
     the final centered approach/stop/[FOUND] check -- the same state
     machine used for every other graded object, including its own
     [RANGE] distance logging as it closes the final ~0.5 m.

climb_stairs() itself is unchanged/untouched. No obstacle avoidance here on
purpose, same as before -- that's a separate optional bonus feature, not
part of this script.

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

# IMPORTANT: (2.9, 2.0), NOT (3.45, 2.0) -- blue_chair's own body is placed
# at EXACTLY (3.45, 2.0, 0.4) (see custom_scene.xml's <body name="blue_chair"
# pos="3.45 2.0 0.4">). A real run climbing straight to (3.45, 2.0) walked
# the robot directly into the chair's own solid collision geometry and got
# it physically wedged there -- trunk_z held steady around 0.70-0.72 m (not
# collapsing, so not a fall) while "dist remaining" stuck at 0.47 m for 3
# segments running, which is climb_stairs()'s own stuck-detection correctly
# catching a robot jammed against something solid, not a locomotion
# failure. Stopping at (2.9, 2.0) instead leaves ~0.55 m of clearance
# before the chair's own footprint, and goto_object() below -- which
# already stops on its own at config.FOUND_DISTANCE_M (0.8 m) -- handles
# closing the remaining distance safely instead of climb_stairs() trying
# to drive through the object it's supposed to stop in front of.
CLIMB_TARGET = (2.9, 2.0)


def _log_blue_chair_range(stage: str, skills, perception) -> None:
    """Grab one frame, look for blue_chair, print [DETECT]/[RANGE] lines
    using the exact same range-estimation helpers navigation.py's own
    goto_object() uses internally -- not a separate/different distance
    computation. navigation._camera_height_above_ground() itself now
    corrects for local (not world-frame) ground clearance via
    skills.get_ground_height_below(), so this script no longer needs
    its own terrain-aware override -- the fix lives in shared code and
    applies to every object/test, not just this one."""
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

        # Detect ONCE, here at the base, before any climbing starts.
        _log_blue_chair_range("at_base", skills, perception)

        print(f"\n>>> Climbing toward {CLIMB_TARGET} (just short of "
              f"blue_chair)...")
        climb_outcome = skills.climb_stairs(
            *CLIMB_TARGET,
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

        print("\n>>> Just short of the chair -- handing off to goto_object() "
              "for the final centered approach/stop...\n")
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
