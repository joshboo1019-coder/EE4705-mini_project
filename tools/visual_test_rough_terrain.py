"""
tools/visual_test_rough_terrain.py — drive the real robot over the UNEVEN
terrain features already present in assets/scenes/custom_scene.xml (they
come from the platform's bundled rc26_track course, imported programmatically
into the scene -- see that file's own header comment and
assets/scenes/README.md), rather than the flat open ground every other
tools/visual_test_task*.py script walks the robot across.

WHY THIS EXISTS: none of the existing visual_test scripts exercise anything
but flat ground + the graded objects. The terrain geoms imported from
rc26_track also include genuine stairs and an uneven "rubble" patch, which
this project had never actually driven the robot across or evaluated --
this script targets those three features specifically, by world (x, y)
coordinates read directly out of custom_scene.xml:

  1. STAIRS_GENTLE  -- a real staircase at y=2.0, x from 1.0 to 5.9: 7 steps
     up (0.05 m each, z 0.025 -> 0.375) to a flat peak at x=3.45, then 7
     steps back down. Step height 0.05 m is small relative to the robot's
     own ~0.33 m standing trunk height, so this is the "should plausibly be
     climbable" case.
  2. STAIRS_STEEP   -- a second staircase at y=6.0, x from 1.4 to 4.5: steps
     of 0.10 m (double STAIRS_GENTLE's) up to a 0.5 m peak at x=2.95. This
     is deliberately the "likely too tall" case -- a single 0.10 m riser is
     a much bigger fraction of this robot's leg clearance, so a stumble or
     outright stall here is an expected, informative result, not just a bug
     to chase.
  3. RUBBLE_PATCH   -- NOT a staircase: a ~1.9 m x 1.8 m grid of ~70 boxes
     at x in [-2.32, -0.43], y in [5.17, 6.90], each with a small random
     roll/pitch (see custom_scene.xml's own geoms in that region) so their
     top surfaces form a continuously uneven, randomly-tilted floor instead
     of flat ground or discrete steps -- the "rough terrain" half of this
     script's name, distinct from the two staircases.

All three are real geoms already baked into the current map (nothing new
added to the scene for this script) -- see custom_scene.xml line references
in the coordinate constants below if you want to cross-check them yourself.

WHAT THIS SCRIPT DOES NOT DO: it does not modify skills_real.py or add any
new SkillsAPI method. Navigation to each feature is done entirely in this
script using the three methods SkillsAPI already exposes
(get_robot_pose(), move(), turn()) plus RealSkills' own get_trunk_height()
diagnostic (same one tools/visual_test_crouch_only.py uses) -- turn-to-face
a world (x, y) waypoint via atan2, then move() straight at it, logging pose
+ trunk height in short segments along the way so the printed trace reads
like a height-over-distance profile across each feature.

THIS HAS NOT BEEN RUN: written from a sandbox with no MuJoCo installed (see
the project's other tools/*.py docstrings for the same caveat). The
waypoint coordinates are read directly from custom_scene.xml's actual
<geom> positions, and move()/turn()'s body-frame-vx / world-yaw convention
matches _yaw_from_wxyz's documented formula (yaw=0 faces +x, positive yaw
turns toward +y) -- but nobody has watched this drive across the real
stairs/rubble yet. Expect to tune SPEED_MPS / SEGMENT_LEN_M after a first
real run, especially for STAIRS_STEEP, which is expected to struggle.

RUN (from the project root):
    python tools/visual_test_rough_terrain.py                     # all three features, in order
    python tools/visual_test_rough_terrain.py --feature stairs_gentle
    python tools/visual_test_rough_terrain.py --feature stairs_steep
    python tools/visual_test_rough_terrain.py --feature rubble
    python tools/visual_test_rough_terrain.py --native             # native MuJoCo window instead of the browser panel

`--gui`/`--native` are mutually exclusive, same convention as every other
tools/visual_test_task*.py script; `--gui` (the browser panel) is the
default and the recommended one to actually watch this on, same reasoning
as those scripts' own docstrings.
"""

import argparse
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.skills_real import RealSkills

# World (x, y) waypoints, read directly off custom_scene.xml's own <geom
# pos="..."> values for each feature (see the module docstring for which
# lines). Each feature is one straight-line walk from an "approach" point
# a little before the feature to a "clear" point a little past it, so the
# whole climb (or attempted climb) happens inside a single straight
# heading -- no steering/re-aiming needed mid-feature.
FEATURES = {
    # custom_scene.xml lines 159-173: 7 steps up (0.05 m each) to a flat
    # peak at x=3.45 z=0.375, then 7 steps back down to x=5.9 -- spans
    # x=[1.0, 5.9] at y=2.0.
    "stairs_gentle": {
        "approach": (0.3, 2.0),
        "clear": (6.4, 2.0),
        "description": "gentle staircase, 0.05 m risers, peak 0.375 m "
                        "(y=2.0 strip, x 1.0->5.9)",
    },
    # custom_scene.xml lines 175-183: steps of 0.10 m up to a 0.5 m peak
    # at x=2.95, spans x=[1.4, 4.5] at y=6.0. Deliberately the "probably
    # too tall" case -- see module docstring.
    "stairs_steep": {
        "approach": (0.9, 6.0),
        "clear": (5.0, 6.0),
        "description": "steep staircase, 0.10 m risers, peak 0.5 m "
                        "(y=6.0 strip, x 1.4->4.5)",
    },
    # custom_scene.xml ~lines 184-320: ~70 boxes with small random
    # roll/pitch, forming a continuously uneven patch rather than discrete
    # steps. Walked diagonally across its longer axis (corner to corner)
    # rather than straight through the middle of one row, so more of the
    # random bumps are actually crossed.
    "rubble": {
        "approach": (0.0, 5.0),
        "clear": (-2.6, 7.1),
        "description": "~1.9x1.8 m randomly-tilted rubble patch "
                        "(x [-2.32,-0.43], y [5.17,6.90])",
    },
}

SPEED_MPS = 0.3          # forward vx per move() segment
SEGMENT_LEN_M = 0.3       # how far each logged segment advances -- short
                          # enough that the printed trunk-height trace
                          # actually resolves individual stair steps
                          # (steps are 0.3-0.5 m deep per custom_scene.xml)
PLAUSIBLE_HEIGHT_RANGE = (0.10, 0.55)  # outside this, flag as a likely
                                       # stumble/launch rather than normal
                                       # stair-climbing variation


def _wrap_deg(angle_deg: float) -> float:
    return (angle_deg + 180.0) % 360.0 - 180.0


def _face(skills: RealSkills, target_x: float, target_y: float) -> None:
    """Closed-loop turn (via skills.turn(), reusing its own [TURN]
    diagnostic) to face a world-frame waypoint, computed the same way
    _yaw_from_wxyz defines yaw in skills_real.py: yaw=0 faces +x, positive
    yaw turns toward +y."""
    pose = skills.get_robot_pose()
    bearing_deg = math.degrees(math.atan2(target_y - pose.y, target_x - pose.x))
    turn_needed = _wrap_deg(bearing_deg - pose.yaw_deg)
    if abs(turn_needed) > 1.0:
        skills.turn(turn_needed)


def _walk_to_with_logging(skills: RealSkills, target_x: float, target_y: float,
                            segment_len: float = SEGMENT_LEN_M,
                            speed: float = SPEED_MPS) -> None:
    """Turn to face (target_x, target_y), then walk straight at it in
    `segment_len`-sized steps, printing pose + trunk height after each
    segment -- this is what turns a single move() into a readable
    height-over-distance trace across a staircase/rubble patch instead of
    one before/after pair that would hide the climb in between."""
    _face(skills, target_x, target_y)

    pose = skills.get_robot_pose()
    total_dist = math.hypot(target_x - pose.x, target_y - pose.y)
    n_segments = max(1, round(total_dist / segment_len))
    actual_segment_len = total_dist / n_segments
    segment_duration = actual_segment_len / speed

    for i in range(n_segments):
        skills.move(vx=speed, vy=0.0, wz=0.0, duration=segment_duration)
        pose = skills.get_robot_pose()
        trunk_z = skills.get_trunk_height()
        dist_remaining = math.hypot(target_x - pose.x, target_y - pose.y)
        flag = ""
        if not (PLAUSIBLE_HEIGHT_RANGE[0] <= trunk_z <= PLAUSIBLE_HEIGHT_RANGE[1]):
            flag = "  <-- trunk_z outside plausible range, possible stumble/launch"
        print(f"    [{i + 1}/{n_segments}] x={pose.x:.2f} y={pose.y:.2f} "
              f"yaw={pose.yaw_deg:.1f} trunk_z={trunk_z:.3f} m "
              f"(dist remaining={dist_remaining:.2f} m){flag}")
    skills.stop()


def run_feature(skills: RealSkills, name: str) -> dict:
    spec = FEATURES[name]
    approach_x, approach_y = spec["approach"]
    clear_x, clear_y = spec["clear"]

    print(f"\n=== {name}: {spec['description']} ===")
    print(f"  Approaching start point ({approach_x}, {approach_y})...")
    _walk_to_with_logging(skills, approach_x, approach_y, segment_len=0.5)

    start_pose = skills.get_robot_pose()
    start_height = skills.get_trunk_height()
    print(f"  At approach point: x={start_pose.x:.2f} y={start_pose.y:.2f} "
          f"yaw={start_pose.yaw_deg:.1f} trunk_z={start_height:.3f} m")
    print(f"  Crossing to ({clear_x}, {clear_y})...")
    _walk_to_with_logging(skills, clear_x, clear_y)

    end_pose = skills.get_robot_pose()
    end_height = skills.get_trunk_height()
    dist_short_of_target = math.hypot(clear_x - end_pose.x, clear_y - end_pose.y)
    heading_drift_deg = abs(_wrap_deg(
        math.degrees(math.atan2(clear_y - approach_y, clear_x - approach_x))
        - end_pose.yaw_deg
    ))

    # Heuristic verdict, not a hard pass/fail -- read the printed segment
    # trace above for the real evidence (a height profile that tracks the
    # staircase's own step heights is the actual result worth reporting;
    # this verdict line is just a quick glance, especially useful for
    # stairs_steep where "fail" is an expected, informative outcome).
    likely_ok = dist_short_of_target < 0.5 and heading_drift_deg < 30.0
    verdict = "reached target, no obvious tip-over/stall" if likely_ok else \
        "did NOT cleanly reach target -- check the segment trace above " \
        "for where it stalled/veered (expected for stairs_steep)"

    print(f"  Result: dist_short_of_target={dist_short_of_target:.2f} m, "
          f"heading_drift={heading_drift_deg:.1f} deg -> {verdict}")

    return {
        "name": name,
        "start_height": start_height,
        "end_height": end_height,
        "dist_short_of_target": dist_short_of_target,
        "heading_drift_deg": heading_drift_deg,
        "likely_ok": likely_ok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature", choices=list(FEATURES) + ["all"], default="all",
                     help="which terrain feature to test (default: all three, "
                          "in order: stairs_gentle, stairs_steep, rubble)")
    ap.add_argument("--native", action="store_true",
                     help="open the native MuJoCo window instead of the "
                          "browser panel (see module docstring)")
    args = ap.parse_args()

    features_to_run = list(FEATURES) if args.feature == "all" else [args.feature]

    print("Booting RealSkills (loads the ONNX policy + opens the MuJoCo scene)...")
    skills = RealSkills(gui=not args.native, native_viewer=args.native)
    # Same try/finally convention as every other tools/visual_test_task*.py
    # script -- see visual_test_task2.py's docstring for why this matters
    # under --native specifically (a background thread keeps calling into
    # the native GLFW window until shutdown() joins it).
    try:
        time.sleep(1.0)  # let the first frame/pose settle before moving

        results = [run_feature(skills, name) for name in features_to_run]

        print("\n=== Summary ===")
        for r in results:
            status = "OK" if r["likely_ok"] else "CHECK"
            print(f"  [{status}] {r['name']}: trunk_z {r['start_height']:.3f} -> "
                  f"{r['end_height']:.3f} m, dist_short_of_target="
                  f"{r['dist_short_of_target']:.2f} m, heading_drift="
                  f"{r['heading_drift_deg']:.1f} deg")

        print("\nDone. Ctrl+C to exit (the sim keeps running otherwise).")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        skills.shutdown()


if __name__ == "__main__":
    main()
