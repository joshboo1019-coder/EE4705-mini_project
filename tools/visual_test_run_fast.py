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

REVISED after a real run: a real run reported the robot wandering into and
getting stuck at a STAIRCASE while this script was running an object-
collision scenario -- not something this script was ever trying to test.
Root cause: each object scenario's approach target was computed dynamically
as "overshoot past the object, as seen from wherever the robot CURRENTLY
is" -- fine right after open_ground, but after a collision the robot's
stopping position is unpredictable, so the straight line from THAT spot to
the next object was never checked against the rest of the scene (stairs,
rubble, the tilted plate -- see tools/visual_test_rough_terrain.py's own
module docstring for all three) and could run through any of them.

Fixed by routing every object approach through a single, fixed STAGING_
POINT (0.0, -3.5) first, instead of chaining straight from wherever the
previous scenario ended. This is deliberately NOT just "closer to the
objects" -- every one of core.config.OBJECT_POSITIONS has x <= -1.3, and
STAGING_POINT's x is 0.0, so BOTH legs (return-to-staging, then staging-to-
object-plus-overshoot) are straight lines between two points that each have
x <= 0, which means the entire line segment stays at x <= 0 too (a straight
line's x never leaves the range of its endpoints' x values). That alone
clears every piece of other scene geometry in this project: stairs_gentle/
stairs_steep both start at x >= 1.0, the tilted plate starts at x >= 0.5,
and rubble's y range (>= 5.17) is never reached either, since every
relevant y value here (staging, all six objects, and up to one overshoot
distance past them) stays well under that. In other words: this isn't a
"probably fine" margin call the way some earlier detours in this project
needed real-run iteration to get right (see stairs_steep's own approach_via
history in visual_test_rough_terrain.py) -- it's a hard geometric guarantee
given these specific coordinates, checked once here rather than something
that needs re-verifying per object.

run_object_scenario() now does the return-to-staging leg itself before
aiming at the object, and reports the object scenario as skipped (not run)
if that return leg doesn't complete cleanly -- starting a collision test
from an unknown, uncontrolled position would defeat the point of having a
known-clear approach in the first place.

REVISED AGAIN after a real run: STAGING_POINT only guarantees clearing
TERRAIN (stairs/plate/rubble -- see the paragraph above), not the other
FIVE graded objects. A real run showed exactly that gap: after the red_
stop_sign scenario, the green_chair scenario's return-to-staging leg (a
straight line from wherever red_stop_sign's approach left the robot, back
to STAGING_POINT) swung back past red_stop_sign itself -- a straight line
between two points that are each individually fine can still clip a THIRD
point neither endpoint is near. The robot got stuck ~0.3 m from red_stop_
sign while simply trying to get back to staging.

Fixed with a small path-planning helper, _safe_route(): before any leg
(return-to-staging OR staging-to-object), it checks the direct line's
clearance (SAFE_MARGIN_M = 0.8 m) against every object in core.config.
OBJECT_POSITIONS except the one this specific leg is allowed to pass close
to (the object actually being approached, for the staging-to-object leg;
nothing, for the return-to-staging leg -- it should clear all six). If the
direct line isn't clear, it tries an L-shaped detour through STAGING_
POINT's own column (x = STAGING_POINT[0]) or row (y = STAGING_POINT[1]) --
one leg of each detour is clear by construction, for the same x<=0 / y<=
-2 reasons as the terrain guarantee above, so only the other leg needs
checking. run_object_scenario() and the staging-return leg both now run
whatever waypoint list _safe_route() returns via a small helper,
_run_waypoints(), instead of a single skills.run_fast() call.

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

# Fixed staging point every object scenario returns to before aiming at its
# object -- see the "REVISED after a real run" paragraph in this module's
# docstring for the full reasoning. In short: every core.config.OBJECT_
# POSITIONS entry has x <= -1.3, and this point's x is 0.0, so any straight
# line between STAGING_POINT and an object (or an overshoot point past it)
# is mathematically guaranteed to stay at x <= 0 the whole way, which
# clears stairs_gentle/stairs_steep (x >= 1.0), the tilted plate
# (x >= 0.5), and rubble (y >= 5.17, never reached at these y-values) --
# not a tuned/guessed value, a geometric guarantee given these coordinates.
STAGING_POINT = (0.0, -3.5)
TRANSIT_X, TRANSIT_Y = STAGING_POINT  # aliases used by _safe_route() below

# REVISED AGAIN after a real run: STAGING_POINT alone only guarantees
# clearing TERRAIN (stairs/plate/rubble, see above) -- it says nothing
# about the OTHER five graded objects. A real run showed the green_chair
# scenario's return-to-staging leg (straight line from wherever red_stop
# sign's scenario left the robot, back to STAGING_POINT) cutting right
# back past red_stop_sign itself -- the two endpoints don't involve red_
# stop_sign at all, but a straight line between them can still pass close
# to a THIRD point that's near neither endpoint. The robot got stuck
# ~0.3 m from red_stop_sign's own (x, y) while just trying to get back to
# staging, not while approaching anything.
#
# SAFE_MARGIN_M is the clearance _safe_route() (below) insists on from
# every object it isn't deliberately aiming at. Deliberately kept just
# UNDER COLLISION_DISTANCE_M (0.6 m, the threshold used elsewhere to
# *detect* a likely collision after the fact): the real run behind this
# fix showed the return leg getting stuck ~0.3 m from an object (clearly
# worth detouring around) while a different, unrelated leg passed ~0.64 m
# from another object and completed with no issue at all -- so a margin
# at or above 0.64 would force a detour (or, worse, an impossible one --
# see the "no clear route" fallback below) around passes that are
# actually fine, while anything under ~0.3-0.5 m is the real danger zone.
SAFE_MARGIN_M = 0.5


def _target_beyond(start_x: float, start_y: float, obj_x: float, obj_y: float,
                    overshoot: float) -> tuple:
    """A point `overshoot` meters past (obj_x, obj_y), as seen from
    (start_x, start_y) -- i.e. continuing straight on the same line.
    run_object_scenario() now always calls this with (start_x, start_y) =
    STAGING_POINT (after first returning there -- see that function and
    the module docstring's "REVISED after a real run" paragraph), so in
    practice this is "overshoot past the object, as seen from the fixed
    staging point" -- kept as a generic start-point function rather than
    hardcoding STAGING_POINT in here, since open_ground has no use for it
    at all."""
    dx = obj_x - start_x
    dy = obj_y - start_y
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        # Already standing on the object's own coordinate -- nothing
        # meaningful to aim past; just return that point itself.
        return obj_x, obj_y
    ux, uy = dx / dist, dy / dist
    return obj_x + ux * overshoot, obj_y + uy * overshoot


def _point_to_segment_dist(px: float, py: float, ax: float, ay: float,
                            bx: float, by: float) -> float:
    """Shortest distance from (px, py) to the line SEGMENT from (ax, ay)
    to (bx, by) -- not the infinite line, so a point only "behind" or
    "past" the segment's ends is measured from the nearest endpoint, not
    an imaginary extension of the line."""
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    proj_x, proj_y = ax + t * dx, ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _segment_clears_objects(ax: float, ay: float, bx: float, by: float,
                             exclude: str = None, margin: float = SAFE_MARGIN_M):
    """True if the straight segment (ax,ay)->(bx,by) stays at least
    `margin` meters from every core.config.OBJECT_POSITIONS entry except
    `exclude` (the one object this particular leg is allowed -- even
    meant -- to pass close to, e.g. the object actually being
    approached). Returns (True, None) or (False, name_of_nearest_offender)."""
    for name, (ox, oy) in config.OBJECT_POSITIONS.items():
        if name == exclude:
            continue
        if _point_to_segment_dist(ox, oy, ax, ay, bx, by) < margin:
            return False, name
    return True, None


def _route_is_clear(ax: float, ay: float, waypoints, exclude: str = None):
    """True if EVERY leg of (ax,ay) -> waypoints[0] -> waypoints[1] -> ...
    stays clear (see _segment_clears_objects), checked explicitly leg by
    leg -- no leg is ever assumed safe "by construction" without this
    actually confirming it, since a detour through STAGING_POINT's own
    column/row only keeps ONE coordinate fixed on ONE leg of a two-leg
    route; the other leg is still a diagonal that needs checking like any
    other."""
    cur_x, cur_y = ax, ay
    for wx, wy in waypoints:
        ok, who = _segment_clears_objects(cur_x, cur_y, wx, wy, exclude=exclude)
        if not ok:
            return False, who
        cur_x, cur_y = wx, wy
    return True, None


def _safe_route(ax: float, ay: float, bx: float, by: float, exclude: str = None):
    """Plan a path from (ax,ay) to (bx,by) as a list of waypoints (NOT
    including the start, always ending with (bx,by)) that stays
    SAFE_MARGIN_M clear of every object except `exclude`.

    REVISED AGAIN after a real run (see the SAFE_MARGIN_M comment above):
    a straight line between two points that are each individually fine
    can still clip a THIRD object neither endpoint is near. Tries the
    direct line first, then a short list of two-leg detours through
    STAGING_POINT's own column/row and through the object endpoints'
    own column/row -- each candidate is verified leg-by-leg via
    _route_is_clear() rather than assumed safe, since (as an earlier,
    buggier version of this function found out) a detour leg that
    happens to have zero length, or isn't actually axis-fixed the way
    it looks, can silently pass a check that doesn't really prove
    anything. Falls back to the direct line (with a printed warning)
    only if no candidate route is fully clear -- seen in this project
    only for legs ending very close to an unrelated object (nothing to
    be done geometrically about that; see the warning text)."""
    direct = [(bx, by)]
    clear, _ = _route_is_clear(ax, ay, direct, exclude=exclude)
    if clear:
        return direct

    candidates = [
        [(TRANSIT_X, ay), (bx, by)],
        [(ax, TRANSIT_Y), (bx, by)],
        [(TRANSIT_X, TRANSIT_Y), (bx, by)],
        [(TRANSIT_X, by), (bx, by)],
        [(bx, TRANSIT_Y), (bx, by)],
    ]
    for route in candidates:
        clear, _ = _route_is_clear(ax, ay, route, exclude=exclude)
        if clear:
            return route

    print(f"  [WARN] _safe_route found no detour that clears every other "
          f"object by {SAFE_MARGIN_M:.1f} m -- falling back to the direct "
          f"line (only checked clear of {exclude!r}). If this leg reports "
          f"'stuck', it may be a different object than the one this "
          f"scenario names, or the target itself may just be close to "
          f"another object -- nothing a route detour alone can fix.")
    return direct


def _run_waypoints(skills: RealSkills, waypoints):
    """Run skills.run_fast() toward each (x, y) in `waypoints` in order,
    stopping at the first leg that doesn't return 'completed'. Returns
    (outcome_of_last_leg_run, final_pose) -- the outcome from whichever
    leg stopped the sequence (or the last one, if every leg completed)."""
    outcome = "completed"
    pose = skills.get_robot_pose()
    for wx, wy in waypoints:
        outcome = skills.run_fast(wx, wy)
        pose = skills.get_robot_pose()
        if outcome != "completed":
            break
    return outcome, pose


def run_open_ground_scenario(skills: RealSkills) -> dict:
    """Baseline, no object in the path -- run_fast() should simply
    complete. Target is a fixed point well clear of every terrain feature
    (assets/scenes/custom_scene.xml's stairs/rubble all sit at x >= -2.32,
    y >= 1.0 -- see tools/visual_test_rough_terrain.py's own module
    docstring) and every graded object (all clustered in x [-4.5, -1.3],
    y [-2.0, 2.0] -- see core/config.py's OBJECT_POSITIONS), so a straight
    run from wherever an earlier scenario left the robot stays open."""
    target_x, target_y = 0.0, -3.5
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
    """Return to STAGING_POINT first (so the approach below always starts
    from a known, scene-clear position regardless of where the previous
    scenario left the robot -- see the "REVISED after a real run"
    docstring paragraph), then aim run_fast() directly at obj_name's own
    registered position (core.config.OBJECT_POSITIONS), continuing
    `overshoot` meters past it -- i.e. deliberately on a collision course,
    since run_fast() has no obstacle avoidance to route around it with.

    If the return-to-staging leg itself doesn't complete cleanly, the
    object approach is skipped rather than run from an unknown position --
    see module docstring."""
    obj_x, obj_y = config.OBJECT_POSITIONS[obj_name]

    stage_x, stage_y = STAGING_POINT
    pre_stage_pose = skills.get_robot_pose()
    print(f"\n=== {obj_name}: returning to staging point "
          f"({stage_x}, {stage_y}) before approaching "
          f"(currently at x={pre_stage_pose.x:.2f} y={pre_stage_pose.y:.2f}) ===")

    # exclude=None: the return leg has no object it's "allowed" to pass
    # close to -- it should clear ALL of them, including whichever one
    # the previous scenario just approached (see SAFE_MARGIN_M comment).
    return_route = _safe_route(pre_stage_pose.x, pre_stage_pose.y,
                                stage_x, stage_y, exclude=None)
    if len(return_route) > 1:
        print(f"  Direct line to staging would pass within {SAFE_MARGIN_M:.1f} m "
              f"of another object -- detouring via {return_route[:-1]} first.")
    stage_outcome, staged_pose = _run_waypoints(skills, return_route)
    dist_from_staging = math.hypot(stage_x - staged_pose.x, stage_y - staged_pose.y)

    if stage_outcome != "completed" or dist_from_staging > COLLISION_DISTANCE_M:
        print(f"  Staging leg result: outcome={stage_outcome!r} "
              f"dist_from_staging_point={dist_from_staging:.2f} m")
        print(f"  Verdict: SKIPPED -- the return-to-staging leg did not "
              f"complete cleanly, so {obj_name} was not approached (an "
              f"uncontrolled starting position would defeat the point of "
              f"having a known-clear approach -- see module docstring).")
        return {
            "name": obj_name,
            "outcome": "skipped",
            "dist_short_of_target": None,
            "dist_to_object": None,
            "start_height": None,
            "end_height": None,
            "likely_collision": False,
        }

    start_pose = staged_pose
    start_height = skills.get_trunk_height()
    target_x, target_y = _target_beyond(start_pose.x, start_pose.y, obj_x, obj_y, overshoot)

    # exclude=obj_name: this leg is DELIBERATELY aimed through obj_name's
    # own position (that's the whole point of this scenario), so it's the
    # one object _safe_route() should NOT detour around -- only check
    # clearance from everything else.
    approach_route = _safe_route(start_pose.x, start_pose.y,
                                  target_x, target_y, exclude=obj_name)
    if len(approach_route) > 1:
        print(f"  Direct line to {obj_name}'s overshoot target would pass "
              f"within {SAFE_MARGIN_M:.1f} m of a DIFFERENT object -- "
              f"detouring via {approach_route[:-1]} first.")

    print(f"  Staged cleanly. Now aiming run_fast() through {obj_name}'s "
          f"own position ({obj_x}, {obj_y}), continuing {overshoot:.1f} m "
          f"past it (target=({target_x:.2f}, {target_y:.2f})) ===")
    print(f"  Starting at x={start_pose.x:.2f} y={start_pose.y:.2f} "
          f"yaw={start_pose.yaw_deg:.1f} trunk_z={start_height:.3f} m")

    outcome, _ = _run_waypoints(skills, approach_route)

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
            elif r["outcome"] == "skipped":
                print(f"  [SKIPPED] {r['name']}: return-to-staging leg did "
                      f"not complete cleanly, object was not approached")
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
