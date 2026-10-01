"""
tools/visual_test_run_fast.py — exercise RealSkills.run_fast() (skills/
skills_real.py's new accelerate/cruise/brake-gently high-speed helper, see
that method's own docstring/class comment) and, specifically, check whether
it collides with a known object instead of avoiding it.

WHY THIS EXISTS: run_fast() has NO obstacle avoidance of its own -- it only
ramps a straight-line (vx, wz) command toward a target point, the same way
move()/turn() always have. That's fine on open ground, but it means if the
straight line from wherever the robot is to run_fast()'s target happens to
pass through a solid object, nothing inside run_fast() will steer around it
or even notice -- it'll just keep commanding forward velocity into whatever
is there. This script deliberately aims run_fast() AT one of this project's
own graded objects (core.config.OBJECT_POSITIONS -- the same chairs/signs/
ball Task 4's perception pipeline is graded on finding), continuing PAST
each object's own coordinate by a fixed overshoot distance, so the
commanded path runs straight through it. Reading the result tells us
whether run_fast() needs obstacle-avoidance added before it's used anywhere
near these objects, or whether (unlikely, given it has none) it happens to
clear them anyway.

HOW A COLLISION IS DETECTED: there is no contact-force sensor exposed by
SkillsAPI/RealSkills to directly ask "did I hit something" -- get_robot_
pose()/get_trunk_height() are the only state this script (or any other
skills_real.py caller) can read. So this script infers a likely collision
from three independent signals, any one of which is suspicious on its own
and together are a reasonably strong tell:
  1. run_fast() not returning "completed" -- it stopped short of finishing
     its own accelerate/cruise/brake profile, consistent with something
     physically blocking forward progress.
  2. The robot's final position landing implausibly close to the object's
     own registered (x, y) -- i.e. it stopped AT the object instead of
     continuing past it by the commanded overshoot, as a clear path would
     have let it do.
  3. A trunk-height jump mid-run -- run_fast() now prints trunk_z every
     segment and flags a single-segment jump over max_height_jump (default
     0.15 m) as "likely impact/stumble", the same delta-based diagnostic
     skills.climb_stairs() already uses for a staircase stumble.
None of these alone is proof (e.g. "incomplete" can also happen from a
plain undershoot with no obstacle at all), which is why the verdict below
reports all three rather than collapsing them into a single boolean.

ALSO INCLUDES an "open_ground" baseline scenario with no object in the
path, run first, specifically so a bad result on an object scenario can be
read correctly: if open_ground ALSO fails, that's evidence of a run_fast()
problem unrelated to collisions (a bug in the method itself), not
something specific to hitting an object.

Nothing here is verified against a real run yet -- same caveat as run_fast()
itself (see its own docstring in skills_real.py): the overshoot distance,
max_height_jump threshold, and the "how close counts as collided" distance
below are first-pass, reasoned defaults, not real-run-tuned values.

RUN (from the project root):
    python tools/visual_test_run_fast.py                                  # open_ground + two objects (default set)
    python tools/visual_test_run_fast.py --scenario open_ground
    python tools/visual_test_run_fast.py --scenario "red_stop sign"
    python tools/visual_test_run_fast.py --scenario "green_chair" "red_chair"
    python tools/visual_test_run_fast.py --scenario all                   # open_ground + every graded object
    python tools/visual_test_run_fast.py --native                        # native MuJoCo window instead of the browser panel

`--gui`/`--native` are mutually exclusive, same convention as every other
tools/visual_test_task*.py script; `--gui` (the browser panel) is the
default and the recommended one to actually watch this on, same reasoning
as those scripts' own docstrings -- seeing the robot actually run into (or
clear) an object is the real evidence here, this script's printed verdict
is only a best-effort proxy for that.
"""

import argparse
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.skills_real import RealSkills
from core import config

# How far past the object's own (x, y) run_fast() is told to aim, measured
# along the straight line from wherever the robot currently is to the
# object -- a clear path would carry the robot this far beyond the
# object's coordinate; stopping well short of that (see "LIKELY COLLIDED"
# reason #2 below) is itself a sign something blocked it.
DEFAULT_OVERSHOOT_M = 1.5

# How close to an object's own registered coordinate counts as "basically
# stopped at/inside it" rather than "still approaching, got cut off by
# max_duration_s for an unrelated reason". Not based on the objects' real
# physical footprints (not available to this script -- OBJECT_POSITIONS is
# just a point, see core/config.py's own comment on it), so this is a
# generous first-pass guess, not a measured object radius.
COLLISION_DISTANCE_M = 0.6

# A single trunk-height jump bigger than this (within one run_fast()
# segment) is flagged by run_fast() itself as "likely impact/stumble" --
# duplicated here only so this script's own verdict text can explain what
# triggered it; the actual detection happens inside run_fast().
MAX_HEIGHT_JUMP_M = 0.15

# Two objects picked for the default scenario set: one close to spawn
# (red_stop sign, (-1.3, 0.0) -- a short, quick first real test) and one a
# little further out in a different direction (green_chair, (-2.0, 2.0)).
# The rest of core.config.OBJECT_POSITIONS are reachable individually via
# --scenario "<name>", or all at once via --scenario all.
DEFAULT_SCENARIOS = ["open_ground", "red_stop sign", "green_chair"]


def _target_beyond(start_x: float, start_y: float, obj_x: float, obj_y: float,
                    overshoot: float) -> tuple:
    """A point `overshoot` meters past (obj_x, obj_y), as seen from
    (start_x, start_y) -- i.e. continuing straight on the same line.
    Computed fresh from the robot's CURRENT position every time this is
    called (not a fixed world coordinate baked into a FEATURES-style
    dict), so the collision test is still valid run-to-run and regardless
    of which scenario happened to run before it and where it left the
    robot -- unlike tools/visual_test_rough_terrain.py's FEATURES dict,
    there's no fixed "approach point" here to make that assumption safe."""
    dx = obj_x - start_x
    dy = obj_y - start_y
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        # Already standing on the object's own coordinate -- nothing
        # meaningful to aim past; just return that point itself.
        return obj_x, obj_y
    ux, uy = dx / dist, dy / dist
    return obj_x + ux * overshoot, obj_y + uy * overshoot


def run_open_ground_scenario(skills: RealSkills) -> dict:
    """Baseline, no object in the path -- run_fast() should simply
    complete. Target is a fixed point well clear of every terrain feature
    (assets/scenes/custom_scene.xml's stairs/rubble all sit at x >= -2.32,
    y >= 1.0 -- see tools/visual_test_rough_terrain.py's own module
    docstring) and every graded object (all clustered in x [-4.5, -1.3],
    y [-2.0, 2.0] -- see core/config.py's OBJECT_POSITIONS), so a straight
    run from wherever an earlier scenario left the robot stays open."""
    target_x, target_y = 3.0, -3.0
    print(f"\n=== open_ground: baseline run_fast() with nothing in the "
          f"path (target=({target_x}, {target_y})) ===")

    start_pose = skills.get_robot_pose()
    start_height = skills.get_trunk_height()
    print(f"  Starting at x={start_pose.x:.2f} y={start_pose.y:.2f} "
          f"yaw={start_pose.yaw_deg:.1f} trunk_z={start_height:.3f} m")

    outcome = skills.run_fast(target_x, target_y)

    end_pose = skills.get_robot_pose()
    end_height = skills.get_trunk_height()
    dist_short_of_target = math.hypot(target_x - end_pose.x, target_y - end_pose.y)

    print(f"  Result: outcome={outcome!r} dist_short_of_target="
          f"{dist_short_of_target:.2f} m trunk_z {start_height:.3f} -> "
          f"{end_height:.3f} m")
    if outcome == "completed":
        print(f"  Verdict: OK -- reached the open-ground target cleanly. "
              f"If an object scenario below fails, this result is what "
              f"rules out 'run_fast() is just broken in general'.")
    else:
        print(f"  Verdict: CHECK -- run_fast() did not cleanly complete "
              f"even with nothing in its path (outcome={outcome!r}). "
              f"Treat any object-scenario failure below as inconclusive "
              f"until this baseline passes -- it may not be the object's "
              f"fault.")

    return {
        "name": "open_ground",
        "outcome": outcome,
        "dist_short_of_target": dist_short_of_target,
        "start_height": start_height,
        "end_height": end_height,
    }


def run_object_scenario(skills: RealSkills, obj_name: str,
                         overshoot: float = DEFAULT_OVERSHOOT_M) -> dict:
    """Aim run_fast() directly at obj_name's own registered position
    (core.config.OBJECT_POSITIONS), continuing `overshoot` meters past it
    -- i.e. deliberately on a collision course, since run_fast() has no
    obstacle avoidance to route around it with."""
    obj_x, obj_y = config.OBJECT_POSITIONS[obj_name]

    start_pose = skills.get_robot_pose()
    start_height = skills.get_trunk_height()
    target_x, target_y = _target_beyond(start_pose.x, start_pose.y, obj_x, obj_y, overshoot)

    print(f"\n=== {obj_name}: run_fast() aimed through its own position "
          f"({obj_x}, {obj_y}), continuing {overshoot:.1f} m past it "
          f"(target=({target_x:.2f}, {target_y:.2f})) ===")
    print(f"  Starting at x={start_pose.x:.2f} y={start_pose.y:.2f} "
          f"yaw={start_pose.yaw_deg:.1f} trunk_z={start_height:.3f} m")

    outcome = skills.run_fast(target_x, target_y)

    end_pose = skills.get_robot_pose()
    end_height = skills.get_trunk_height()
    dist_short_of_target = math.hypot(target_x - end_pose.x, target_y - end_pose.y)
    dist_to_object = math.hypot(obj_x - end_pose.x, obj_y - end_pose.y)
    height_delta = end_height - start_height

    reasons = []
    if outcome == "stuck":
        reasons.append(
            f"run_fast() returned 'stuck' -- its own stuck-detector caught "
            f"forward progress stalling out (well short of what the "
            f"commanded vx implied) for several segments running, the "
            f"most direct signal this script can get of a real collision")
    elif outcome != "completed":
        reasons.append(
            f"run_fast() returned {outcome!r} instead of 'completed' -- it "
            f"did not finish its own accelerate/cruise/brake profile, "
            f"consistent with forward progress getting physically blocked")
    if dist_to_object < COLLISION_DISTANCE_M:
        reasons.append(
            f"ended only {dist_to_object:.2f} m from {obj_name}'s own "
            f"position (< {COLLISION_DISTANCE_M:.1f} m) -- a clear path "
            f"would have carried it {overshoot:.1f} m past that point, "
            f"not stopped at/inside it")
    if abs(height_delta) > MAX_HEIGHT_JUMP_M:
        reasons.append(
            f"trunk height moved {height_delta:+.3f} m start-to-end "
            f"(start {start_height:.3f} m -> end {end_height:.3f} m) -- "
            f"check the per-segment [RUN] trace above for which specific "
            f"segment's trunk_z jump run_fast() itself flagged")

    likely_collision = len(reasons) > 0
    verdict = "LIKELY COLLIDED" if likely_collision else \
        "no clear sign of collision (cleared the object or missed it)"

    print(f"  Result: outcome={outcome!r} dist_short_of_target="
          f"{dist_short_of_target:.2f} m dist_to_{obj_name.replace(' ', '_')}="
          f"{dist_to_object:.2f} m trunk_z {start_height:.3f} -> "
          f"{end_height:.3f} m")
    for r in reasons:
        print(f"    -- {r}")
    print(f"  Verdict: {verdict}")

    return {
        "name": obj_name,
        "outcome": outcome,
        "dist_short_of_target": dist_short_of_target,
        "dist_to_object": dist_to_object,
        "start_height": start_height,
        "end_height": end_height,
        "likely_collision": likely_collision,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", nargs="+",
                     choices=["open_ground", "all"] + list(config.OBJECT_POSITIONS),
                     default=DEFAULT_SCENARIOS,
                     help="which scenario(s) to run -- 'open_ground' (no "
                          "object, baseline), one or more object names from "
                          "core.config.OBJECT_POSITIONS (quote names with a "
                          "space, e.g. \"red_stop sign\"), or 'all' (open_"
                          "ground plus every graded object). Default: "
                          f"{DEFAULT_SCENARIOS!r}.")
    ap.add_argument("--overshoot", type=float, default=DEFAULT_OVERSHOOT_M,
                     help=f"how far past each object's own position to aim "
                          f"run_fast() at, in meters (default "
                          f"{DEFAULT_OVERSHOOT_M}).")
    ap.add_argument("--native", action="store_true",
                     help="open the native MuJoCo window instead of the "
                          "browser panel (see module docstring)")
    args = ap.parse_args()

    if "all" in args.scenario:
        scenarios_to_run = ["open_ground"] + list(config.OBJECT_POSITIONS)
    else:
        # Keep "open_ground" first if present, regardless of the order
        # typed, since it's meant to run before any object scenario (see
        # module docstring -- it's the baseline the object results are
        # read against).
        selected = list(dict.fromkeys(args.scenario))  # de-dup, keep order
        if "open_ground" in selected:
            selected.remove("open_ground")
            scenarios_to_run = ["open_ground"] + selected
        else:
            scenarios_to_run = selected

    print("Booting RealSkills (loads the ONNX policy + opens the MuJoCo scene)...")
    skills = RealSkills(gui=not args.native, native_viewer=args.native)
    try:
        time.sleep(1.0)  # let the first frame/pose settle before moving

        results = []
        for name in scenarios_to_run:
            if name == "open_ground":
                result = run_open_ground_scenario(skills)
            else:
                result = run_object_scenario(skills, name, overshoot=args.overshoot)
            results.append(result)

        print("\n=== Summary ===")
        for r in results:
            if r["name"] == "open_ground":
                status = "OK" if r["outcome"] == "completed" else "CHECK"
                print(f"  [{status}] open_ground: outcome={r['outcome']!r} "
                      f"dist_short_of_target={r['dist_short_of_target']:.2f} m "
                      f"trunk_z {r['start_height']:.3f} -> {r['end_height']:.3f} m")
            else:
                status = "COLLIDED" if r["likely_collision"] else "OK"
                print(f"  [{status}] {r['name']}: outcome={r['outcome']!r} "
                      f"dist_to_object={r['dist_to_object']:.2f} m "
                      f"trunk_z {r['start_height']:.3f} -> {r['end_height']:.3f} m")

        print("\nDone. Ctrl+C to exit (the sim keeps running otherwise).")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        skills.shutdown()


if __name__ == "__main__":
    main()
