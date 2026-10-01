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

None of these three is a target by itself, but there is a FOURTH terrain
geom in the scene, between stairs_gentle and stairs_steep/rubble, that
this script does NOT target or test directly -- a single tilted plate at
custom_scene.xml's <geom pos="2.0 4.0 0.1" type="box" size="1.5 0.75
0.005" quat="0.995 0 -0.0998 0">, i.e. x in [0.5, 3.5], y in [3.25, 4.75],
tilted roughly 11.5 deg (from the quaternion). It was missed entirely in
this script's first two "safe corridor between features" assumptions
(see stairs_steep's own "approach_via" comment below for the real-run
failures that found it the hard way) -- it is NOT one of this script's
three named features, but any waypoint chosen between stairs_gentle and
stairs_steep/rubble has to route around it.

All four are real geoms already baked into the current map (nothing new
added to the scene for this script) -- see custom_scene.xml line references
in the coordinate constants below if you want to cross-check them yourself.

WHAT THIS SCRIPT DOES NOT DO: it does not modify skills_real.py's own
move()/turn()/get_robot_pose()/get_trunk_height() (the raw SkillsAPI-level
primitives) or add any new SkillsAPI method. The actual waypoint-navigation
logic -- re-aiming every segment, the delta-based stumble flag, the
width-based edge-drift guard, and the stuck-detector -- now lives directly
on RealSkills itself as skills.climb_stairs()/skills.cross_rough_terrain()
(see skills/skills_real.py's own "Terrain traversal" section for the full
history of why each of those exists). This script is now just the choreography
around those two methods: the FEATURES waypoints, calling the right method
for each feature, and printing a run summary -- it carries no copy of the
segment-walking loop anymore.

VERIFIED AGAINST A REAL RUN (2026-10-01, team's WSL2 laptop, --native):
the first version of this script (its own single _face() call per crossing,
no width guard) correctly surfaced a real failure -- on stairs_gentle, a
step-edge-induced yaw nudge around x=1.17 went uncorrected for the rest of
the ~6 m crossing, drifted the robot's y steadily from 1.89 toward the
strip's actual y=3.0 edge, and it walked off the side before reaching the
far end (confirmed by eye, not just inferred from the logged trunk_z
spike to 0.69 m). A second real run (after adding re-facing-every-segment
and the width guard, both now part of skills.climb_stairs() itself) showed
heading drift down from 15.7-22+ deg to 4.9 deg with no edge-drift abort on
stairs_gentle, but also surfaced two more real issues, both now handled
inside skills_real.py's terrain-traversal engine: a trunk_z absolute-range
false positive right at the staircase peak (fixed by making the stumble
check delta-based, not absolute), and a cascading stuck/fallen state when
chaining multiple features in one process with no reset between them
(see skills_real.py's own comments and the multi-feature warning in main()
below).

A third real run (after making the engine walk each feature to actual
arrival instead of a fixed segment budget, and making main() stop rather
than chain onward from an unfinished feature) confirmed BOTH of those
fixes working: stairs_gentle genuinely completed this time (29 segments,
not the originally-budgeted ~20 -- dist_short_of_target=0.13 m), and when
stairs_steep's approach then got stuck for a real, different reason (see
next paragraph), the script correctly stopped there instead of continuing
to rubble from a fallen robot. That run surfaced a THIRD real issue,
since fixed via stairs_steep's own "approach_via" detour waypoints (see
FEATURES above): the straight line from stairs_gentle's own end point to
stairs_steep's approach point cut diagonally back through stairs_gentle's
own strip, and the robot caught a step edge while turned around mid-turn,
tipping over (trunk_z collapsed to ~0.21 m, then genuinely stuck). Only
reproducible when stairs_steep runs right after stairs_gentle
(--feature all); running it alone starts from spawn and never approaches
stairs_gentle's strip in the first place.

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
        # When run right after stairs_gentle (--feature all), a straight
        # line from stairs_gentle's own end point (~6.3, 2.0) to this
        # feature's approach point (0.9, 6.0) cuts diagonally back
        # through stairs_gentle's own strip (x [1.0,5.9], y [1.0,3.0]) --
        # a real run confirmed this actually happens (the line crosses
        # y=3.0 around x=4.9, still inside that x range) and caught a
        # step edge while the robot was turned around mid-turn, tipping
        # it over (trunk_z collapsed to ~0.21 m, then stuck).
        #
        # First fix attempt routed around stairs_gentle via (6.4, 3.5)
        # then (6.4, 6.0) -- clear of stairs_gentle, but a real run then
        # showed the NEXT leg (that waypoint, east of stairs_steep's own
        # x=4.5, straight to the approach point at x=0.9, WEST of
        # stairs_steep's x=1.4) walks the full LENGTH of stairs_steep's
        # own staircase -- i.e. the "approach" was accidentally doing
        # stairs_steep's climb itself, and got stuck partway (x=4.54,
        # right at the staircase's own far edge) well before the actual
        # crossing phase even started.
        #
        # Second fix attempt detoured WEST of both staircases at x=0.3,
        # routed at y=3.5, then y=4.2 after the first of those also got
        # stuck. BOTH got stuck at almost the identical x (~3.45-3.6)
        # despite the y change -- which, in hindsight, was the real tell:
        # a y-margin problem against stairs_gentle's edge would have
        # moved (or fixed) the failure point when y changed; getting
        # stuck at the same x regardless of y instead means a SEPARATE,
        # stationary obstacle at that x column. Checking custom_scene.xml
        # directly (rather than continuing to guess margins) found it: a
        # tilted plate at <geom pos="2.0 4.0 0.1" size="1.5 0.75 0.005"
        # quat="0.995 0 -0.0998 0"> -- x in [0.5, 3.5], y in [3.25, 4.75],
        # ~11.5 deg tilted -- that neither of those "safe corridor"
        # y values (3.5 and 4.2) was actually clear of. It isn't one of
        # this script's three named features (see the module docstring),
        # which is exactly how it got missed in the first two attempts.
        #
        # Fixed below with a 4-waypoint route that stays clear of all
        # four known geoms (stairs_gentle, the tilted plate, stairs_steep,
        # and rubble) at every leg, not just the two staircases:
        #   (6.4, 4.2):  east of stairs_gentle (x<=5.9), the plate
        #                (x<=3.5) and stairs_steep (x<=4.5) -- x alone
        #                clears all three regardless of y, same as the
        #                first detour leg both earlier attempts already
        #                verified working.
        #   (6.4, 5.0):  still x=6.4 (same reasoning), y raised to 5.0 to
        #                line up for the crossing leg below.
        #   (0.0, 5.0):  the x-decreasing leg, at y=5.0 -- the one gap in
        #                y that clears BOTH the plate (ends at y=4.75,
        #                0.25 m clear) and stairs_steep (starts at
        #                y=5.25, 0.25 m clear) at once; x=0.0 matches
        #                rubble's own "clear" approach point below, since
        #                rubble's own x only reaches -0.43 (0.43 m clear)
        #                and the plate's x starts at 0.5 (0.5 m clear).
        #   (0.0, 6.0):  x=0.0 stays clear of the plate (x<=3.5) and
        #                stairs_steep (x>=1.4) the whole way north to
        #                y=6.0, and clear of rubble (x<=-0.43) throughout.
        # Only matters for --feature all/when run after stairs_gentle;
        # run alone (--feature stairs_steep) the robot starts at spawn
        # (0,0) and never gets near any of this, so the detour is just
        # harmless extra distance either way. The y=5.0 crossing leg has
        # the tightest margins here (0.25 m each side, a real structural
        # gap between the plate and stairs_steep, not a guess) -- if a
        # future run still catches an edge there, the fix is routing
        # around at larger x (east of stairs_steep too) rather than
        # trying to thread an even narrower gap.
        "approach_via": [(6.4, 4.2), (6.4, 5.0), (0.0, 5.0), (0.0, 6.0)],
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


def run_feature(skills: RealSkills, name: str) -> dict:
    spec = FEATURES[name]
    approach_x, approach_y = spec["approach"]
    clear_x, clear_y = spec["clear"]

    print(f"\n=== {name}: {spec['description']} ===")

    # Some features need a detour on the way to their own approach point
    # (see "approach_via" in FEATURES -- stairs_steep's own comment above
    # explains why) rather than one straight line from wherever the
    # previous feature left the robot, which can cut back through
    # terrain already crossed. Walk each via-waypoint first, same engine
    # as the final approach leg; the first one that doesn't actually
    # finish aborts the whole approach (same handling as the final leg
    # below), since continuing past an unfinished detour leg is exactly
    # the "chain forward from a bad state" problem this script no longer
    # does.
    approach_outcome = "completed"
    for via_x, via_y in spec.get("approach_via", []):
        print(f"  Detouring via ({via_x}, {via_y})...")
        approach_outcome = skills.cross_rough_terrain(via_x, via_y, segment_len=0.5)
        if approach_outcome != "completed":
            break

    if approach_outcome == "completed":
        print(f"  Approaching start point ({approach_x}, {approach_y})...")
        # The approach walk never needs the width guard (it's just getting
        # to the feature's own start line over presumably-flat ground), so
        # it always goes through cross_rough_terrain() regardless of which
        # feature this is -- same engine as climb_stairs(), just without
        # width_axis/width_center/width_limit.
        approach_outcome = skills.cross_rough_terrain(
            approach_x, approach_y, segment_len=0.5
        )

    start_pose = skills.get_robot_pose()
    start_height = skills.get_trunk_height()
    print(f"  At approach point: x={start_pose.x:.2f} y={start_pose.y:.2f} "
          f"yaw={start_pose.yaw_deg:.1f} trunk_z={start_height:.3f} m")

    if approach_outcome != "completed":
        # Don't even attempt the crossing if the approach itself didn't
        # actually finish ("stuck" or "incomplete") -- a real run showed
        # why: the "crossing" of a feature whose approach never properly
        # arrived produces a width-guard trip for the wrong reason (it
        # reads as "drifted off mid-crossing" when it actually never got
        # there). skills.cross_rough_terrain() now keeps walking until it
        # truly arrives rather than giving up after a fixed segment
        # count, so a "stuck"/"incomplete" here means a real failure
        # (tipped/wedged, or a genuine endless drift), not just "ran out
        # of its turn" -- which is exactly why this feature's run stops
        # here instead of pretending to test the crossing anyway.
        print(f"  Skipping the crossing -- the approach walk did not "
              f"actually finish (outcome={approach_outcome!r}, see the "
              f"'!!' line above). re-run with --feature {name} on its "
              f"own, starting fresh from spawn, to get an independent "
              f"result.")
        return {
            "name": name,
            "start_height": start_height,
            "end_height": start_height,
            "dist_short_of_target": math.hypot(clear_x - start_pose.x,
                                                 clear_y - start_pose.y),
            "heading_drift_deg": 0.0,
            "outcome": f"{approach_outcome}_before_crossing",
            "likely_ok": False,
        }

    print(f"  Crossing to ({clear_x}, {clear_y})...")
    if "width_axis" in spec:
        # stairs_gentle / stairs_steep: a real strip with a fall-off-the-
        # side edge, so cross via climb_stairs() with the width guard.
        outcome = skills.climb_stairs(
            clear_x, clear_y,
            width_axis=spec["width_axis"],
            width_center=spec["width_center"],
            width_limit=spec["width_limit"],
        )
    else:
        # rubble: an open patch, no edge to guard against.
        outcome = skills.cross_rough_terrain(clear_x, clear_y)

    end_pose = skills.get_robot_pose()
    end_height = skills.get_trunk_height()
    dist_short_of_target = math.hypot(clear_x - end_pose.x, clear_y - end_pose.y)
    heading_drift_deg = abs(_wrap_deg(
        math.degrees(math.atan2(clear_y - approach_y, clear_x - approach_x))
        - end_pose.yaw_deg
    ))

    # Heuristic verdict, not a hard pass/fail -- read the printed segment
    # trace above (from inside skills.climb_stairs()/cross_rough_terrain())
    # for the real evidence (a height profile that tracks the staircase's
    # own step heights is the actual result worth reporting; this verdict
    # line is just a quick glance, especially useful for stairs_steep
    # where "fail" is an expected, informative outcome).
    if outcome == "edge_drift":
        verdict = "aborted -- drifted off the structure's side edge " \
            "(see the '!!' line above); a lateral-drift failure, not " \
            "necessarily a height/balance one"
        likely_ok = False
    elif outcome == "stuck":
        verdict = "aborted -- robot stopped making forward progress " \
            "mid-crossing (see the '!!' line above); likely tipped/" \
            "wedged, not merely struggling with the terrain"
        likely_ok = False
    elif outcome == "incomplete":
        verdict = "aborted -- still short of the target after a generous " \
            "segment budget (see the '!!' line above); it WAS still " \
            "making progress, just too slowly/unpredictably to finish " \
            "(expected for stairs_steep)"
        likely_ok = False
    else:
        # outcome == "completed": the engine only returns this once the
        # robot is actually within arrival_tolerance of the target, so
        # this check is a sanity check on that, not the primary verdict.
        likely_ok = dist_short_of_target < 0.5 and heading_drift_deg < 30.0
        verdict = "reached target, no obvious tip-over/stall" if likely_ok else \
            "reached the target but with a larger heading drift than " \
            "expected -- check the segment trace above"

    print(f"  Result: dist_short_of_target={dist_short_of_target:.2f} m, "
          f"heading_drift={heading_drift_deg:.1f} deg -> {verdict}")

    return {
        "name": name,
        "start_height": start_height,
        "end_height": end_height,
        "dist_short_of_target": dist_short_of_target,
        "heading_drift_deg": heading_drift_deg,
        "outcome": outcome,
        "likely_ok": likely_ok,
    }


def _wrap_deg(angle_deg: float) -> float:
    return (angle_deg + 180.0) % 360.0 - 180.0


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

    if len(features_to_run) > 1:
        # RealSkills/the platform has no exposed way to reset the robot's
        # pose from a script (only platform.reset_robot(), wired to the
        # browser panel's Reset button / 'T' key, consumed via
        # self._runtime.consume_reset() -- not callable from here). A
        # real --feature all run showed what that costs: stairs_gentle's
        # own crossing used up its (back then, fixed) segment budget
        # while still genuinely climbing, 2.71 m short of the target,
        # and the script moved on to stairs_steep anyway, starting its
        # approach from that unfinished, still-on-the-stairs position --
        # which then went straight into an unrelated-looking failure.
        # Two things now guard against exactly that:
        #   1. skills.climb_stairs()/cross_rough_terrain() keep walking
        #      each feature until the robot actually ARRIVES (or a real
        #      stuck/edge_drift failure is caught) rather than giving up
        #      after a fixed segment count -- so "ran out of its turn"
        #      can no longer happen on its own.
        #   2. main() below now STOPS running further features the
        #      moment one doesn't come back "completed" (see the loop
        #      below), instead of chaining onward from an unfinished or
        #      fallen position regardless.
        print("NOTE: running multiple features in one process with no "
              "reset between them -- each feature now runs to actual "
              "completion before the next one starts (see skills_real.py's "
              "own terrain-traversal engine), and this script stops "
              "entirely, rather than continuing to the next feature, the "
              "moment one doesn't finish cleanly -- a bad outcome on one "
              "feature still can't silently carry into the next one's "
              "result. For a fully independent run of every feature "
              "regardless of outcome, run each --feature separately "
              "instead of --feature all.\n")

    print("Booting RealSkills (loads the ONNX policy + opens the MuJoCo scene)...")
    skills = RealSkills(gui=not args.native, native_viewer=args.native)
    # Same try/finally convention as every other tools/visual_test_task*.py
    # script -- see visual_test_task2.py's docstring for why this matters
    # under --native specifically (a background thread keeps calling into
    # the native GLFW window until shutdown() joins it).
    try:
        time.sleep(1.0)  # let the first frame/pose settle before moving

        results = []
        for name in features_to_run:
            result = run_feature(skills, name)
            results.append(result)
            # Only move on to the next feature once this one has
            # actually completed -- anything else (stuck/edge_drift/
            # incomplete, or a skipped crossing because the approach
            # itself didn't finish) means the robot is in a state that
            # would corrupt the next feature's result, so stop here
            # rather than chaining onward from it. The walk itself
            # already blocks/loops until the robot truly arrives (or a
            # real failure is caught) before run_feature() even returns
            # -- this check is what decides whether to START the next
            # one, not what makes the current one wait.
            if result["outcome"] != "completed" and name != features_to_run[-1]:
                print(f"\nStopping here -- {name} did not complete "
                      f"(outcome={result['outcome']!r}), so the remaining "
                      f"feature(s) ({', '.join(features_to_run[features_to_run.index(name) + 1:])}) "
                      f"are being skipped rather than run from this "
                      f"unfinished position. Re-run with --feature "
                      f"<name> to test any of them independently.")
                break

        print("\n=== Summary ===")
        for r in results:
            status = "OK" if r["likely_ok"] else "CHECK"
            outcome_note = "" if r["outcome"] == "completed" else f"  ({r['outcome']})"
            print(f"  [{status}] {r['name']}: trunk_z {r['start_height']:.3f} -> "
                  f"{r['end_height']:.3f} m, dist_short_of_target="
                  f"{r['dist_short_of_target']:.2f} m, heading_drift="
                  f"{r['heading_drift_deg']:.1f} deg{outcome_note}")

        print("\nDone. Ctrl+C to exit (the sim keeps running otherwise).")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        skills.shutdown()


if __name__ == "__main__":
    main()
