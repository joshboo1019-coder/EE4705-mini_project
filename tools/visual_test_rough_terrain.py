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
diagnostic (same one tools/visual_test_crouch_only.py uses) -- re-aiming at
the target waypoint via atan2 before every short move() segment (not just
once at the start -- see _walk_to_with_logging's own docstring for why
that changed after a real run), logging pose + trunk height after each
segment so the printed trace reads like a height-over-distance profile
across each feature. stairs_gentle/stairs_steep also carry a width_axis/
width_center/width_limit in FEATURES below: the crossing aborts (and says
so) the moment the robot drifts past that margin off the strip's own
centerline, rather than continuing to log meaningless pose data after it's
already walked off the structure's side edge.

VERIFIED AGAINST A REAL RUN (2026-10-01, team's WSL2 laptop, --native):
the first version of this script (single _face() call per crossing, no
width guard) correctly surfaced a real failure -- on stairs_gentle, a
step-edge-induced yaw nudge around x=1.17 went uncorrected for the rest of
the ~6 m crossing, drifted the robot's y steadily from 1.89 toward the
strip's actual y=3.0 edge, and it walked off the side before reaching the
far end (confirmed by eye, not just inferred from the logged trunk_z
spike to 0.69 m). The continuous re-facing and width-abort above are the
fix, informed by that run -- but re-facing every segment hasn't itself
been run yet, so the usual caveat still applies to whether it's enough to
keep the robot centered through a real climb (as opposed to just detecting
a side-drift sooner). Expect to tune SPEED_MPS / SEGMENT_LEN_M / each
feature's width_limit after trying it.

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
    # x=[1.0, 5.9] at y=2.0. Step geoms are size="0.15 1.0 0.025" -> 1.0 m
    # half-width in y, so the usable strip is y=[1.0, 3.0] around the
    # y=2.0 centerline. width_limit below is that half-width minus a
    # margin for the robot's own footprint, so a drift-off-the-side is
    # flagged a bit before the robot is actually past the physical edge.
    "stairs_gentle": {
        "approach": (0.3, 2.0),
        "clear": (6.4, 2.0),
        "description": "gentle staircase, 0.05 m risers, peak 0.375 m "
                        "(y=2.0 strip, x 1.0->5.9)",
        "width_axis": "y",
        "width_center": 2.0,
        "width_limit": 0.8,
    },
    # custom_scene.xml lines 175-183: steps of 0.10 m up to a 0.5 m peak
    # at x=2.95, spans x=[1.4, 4.5] at y=6.0. Step geoms are size="0.15
    # 0.75 ..." -> 0.75 m half-width in y (narrower than stairs_gentle's
    # strip), so the margin below is tighter. Deliberately the "probably
    # too tall" case -- see module docstring.
    "stairs_steep": {
        "approach": (0.9, 6.0),
        "clear": (5.0, 6.0),
        "description": "steep staircase, 0.10 m risers, peak 0.5 m "
                        "(y=6.0 strip, x 1.4->4.5)",
        "width_axis": "y",
        "width_center": 6.0,
        "width_limit": 0.55,
    },
    # custom_scene.xml ~lines 184-320: ~70 boxes with small random
    # roll/pitch, forming a continuously uneven patch rather than discrete
    # steps. Walked diagonally across its longer axis (corner to corner)
    # rather than straight through the middle of one row, so more of the
    # random bumps are actually crossed. No width_axis/limit here -- it's
    # an open patch, not a narrow strip with a fall-off edge, so there's
    # no equivalent "walked off the side" failure mode to guard against.
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
                            speed: float = SPEED_MPS,
                            width_axis: str = None, width_center: float = None,
                            width_limit: float = None) -> bool:
    """Walk toward (target_x, target_y) in `segment_len`-sized segments,
    printing pose + trunk height after each one.

    Re-aims at the target with _face() before EVERY segment, not just
    once up front. An earlier version only called _face() once before the
    whole crossing -- fine on flat ground, but on a staircase a single
    step-edge-induced yaw nudge (the policy has no terrain-height input,
    so it can't anticipate or correct for a leg catching an edge) then
    went uncorrected for the rest of the crossing and compounded into a
    steady sideways drift. A real run confirmed this: yaw climbed from 0
    to 22 deg over ~15 segments on stairs_gentle, and the robot walked
    off the staircase's own side edge (y drifted from 1.89 toward the
    strip's actual y=3.0 edge) before ever reaching the far end. Re-facing
    every segment is the standard fix (equivalent to perception/
    navigation.py's own steer-to-center loop, just steering toward a
    world waypoint instead of a bbox center) -- it can't undo a stumble
    that already happened, but it stops a small heading error from ever
    accumulating into a walk-off-the-edge in the first place.

    If width_axis/width_center/width_limit are given (stairs_gentle/
    stairs_steep only -- see FEATURES), aborts early and returns False
    the moment the robot's position along width_axis strays past
    width_limit from width_center, instead of continuing to log pose data
    after it's already fallen off the side (that data is meaningless --
    once it's off the structure entirely, trunk_z/yaw no longer describe
    "how is the climb going"). Returns True if the full distance was
    covered without tripping that guard."""
    pose = skills.get_robot_pose()
    total_dist = math.hypot(target_x - pose.x, target_y - pose.y)
    n_segments = max(1, round(total_dist / segment_len))
    actual_segment_len = total_dist / n_segments
    segment_duration = actual_segment_len / speed

    for i in range(n_segments):
        _face(skills, target_x, target_y)
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

        if width_axis is not None:
            lateral = pose.y if width_axis == "y" else pose.x
            if abs(lateral - width_center) > width_limit:
                print(f"    !! drifted {width_axis}={lateral:.2f} past the "
                      f"+/-{width_limit:.2f} m margin around "
                      f"{width_axis}={width_center:.2f} -- stopping before "
                      f"it walks off the structure's edge")
                skills.stop()
                return False
    skills.stop()
    return True


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
    completed = _walk_to_with_logging(
        skills, clear_x, clear_y,
        width_axis=spec.get("width_axis"),
        width_center=spec.get("width_center"),
        width_limit=spec.get("width_limit"),
    )

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
    if not completed:
        verdict = "aborted -- drifted off the structure's side edge " \
            "(see the '!!' line above); not a height/balance failure " \
            "at that point, a lateral-drift one"
        likely_ok = False
    else:
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
        "completed": completed,
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
            edge_note = "" if r["completed"] else "  (aborted: drifted off edge)"
            print(f"  [{status}] {r['name']}: trunk_z {r['start_height']:.3f} -> "
                  f"{r['end_height']:.3f} m, dist_short_of_target="
                  f"{r['dist_short_of_target']:.2f} m, heading_drift="
                  f"{r['heading_drift_deg']:.1f} deg{edge_note}")

        print("\nDone. Ctrl+C to exit (the sim keeps running otherwise).")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        skills.shutdown()


if __name__ == "__main__":
    main()
