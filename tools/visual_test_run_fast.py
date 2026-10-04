# Owner: Student A (Task 2)
"""
tools/visual_test_run_fast.py — exercise RealSkills.run_fast() (skills/
skills_real.py's new accelerate/cruise/brake-gently high-speed helper, see
that method's own docstring/class comment) by touring it through this
project's graded objects, treating getting close to each one as "reached"
and moving on to the next -- see the "REVISED AGAIN: from collision test to
waypoint tour" paragraph below for how this script's purpose changed and
why the ORIGINAL design (summarized next) aimed deliberately THROUGH each
object instead.

WHY THIS EXISTS (ORIGINAL DESIGN): run_fast() has NO obstacle avoidance of
its own -- it only ramps a straight-line (vx, wz) command toward a target
point, the same way move()/turn() always have. That's fine on open ground,
but it means if the straight line from wherever the robot is to run_fast()'s
target happens to pass through a solid object, nothing inside run_fast()
will steer around it or even notice -- it'll just keep commanding forward
velocity into whatever is there. This script ORIGINALLY aimed run_fast() AT
one of this project's own graded objects (core.config.OBJECT_POSITIONS --
the same chairs/signs/ball Task 4's perception pipeline is graded on
finding), continuing PAST each object's own coordinate by a fixed overshoot
distance, so the commanded path ran straight through it, specifically to
find out whether run_fast() needs obstacle-avoidance added before it's used
anywhere near these objects. Real runs confirmed that it does (see the
real-run history below) -- that question is now answered, so the script's
job changed (see "REVISED AGAIN" below): rather than keep proving the same
thing, it now tours the objects as waypoints to reach and move past.

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

REVISED AGAIN: from collision test to waypoint tour. The original design
(above) deliberately overshot THROUGH each object to answer "does run_fast()
collide with things in its path" -- and real runs answered that: it does
(one run ended stuck 0.29 m from red_stop_sign, a genuine collision; see
the project's own run history for that result). With that question settled,
continuing to aim through objects by default just risks more of the same
collision every run, for no new information. The script's purpose changed:
each object scenario now aims at a point ARRIVAL_DISTANCE_M short of the
object (see that constant's own comment -- it matches core.config.
FOUND_DISTANCE_M, the same "close enough" threshold Task 4's own approach
logic uses), and once run_fast() completes that approach, treats the object
as REACHED and moves on to the next objective in the scenario list (or ends,
if it was the last one) -- see run_object_scenario()'s own docstring and
main()'s scenario loop. A result still gets flagged (not "REACHED") if
run_fast() doesn't complete the approach at all (stuck/timeout before
reaching the stand-off point) or if it ends up suspiciously CLOSER than
arrival_distance -- that would mean it pushed past its own intended
stopping point and into the object, still a real collision despite the
softer target. The old overshoot-through-it behavior isn't kept as a CLI
option here -- if a from-scratch collision re-test is ever needed again,
_target_before()'s sibling _target_beyond() logic (negate stop_short) is a
two-line revert away, but isn't wired up since it isn't what this script is
for anymore.

RUN (from the project root):
    python tools/visual_test_run_fast.py                                  # open_ground + red_stop sign (default set)
    python tools/visual_test_run_fast.py --scenario open_ground
    python tools/visual_test_run_fast.py --scenario "red_stop sign"
    python tools/visual_test_run_fast.py --scenario "green_chair" "red_chair"
    python tools/visual_test_run_fast.py --scenario all                   # open_ground + every graded object, in order
    python tools/visual_test_run_fast.py --arrival-distance 0.5           # stop closer before calling an object reached
    python tools/visual_test_run_fast.py --native                        # native MuJoCo window instead of the browser panel

`--gui`/`--native` are mutually exclusive, same convention as every other
tools/visual_test_task*.py script; `--gui` (the browser panel) is the
default and the recommended one to actually watch this on, same reasoning
as those scripts' own docstrings -- seeing the robot actually approach (or
fail to reach) an object is the real evidence here, this script's printed
verdict is only a best-effort proxy for that.
"""

import argparse
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.skills_real import RealSkills
from core import config

# REVISED: this script no longer aims run_fast() THROUGH each object and
# past it -- that deliberate-collision-course design (the ORIGINAL ~1.5 m
# overshoot behavior, see the module docstring's early history) answered
# "does run_fast() collide with things in its path" and it does (confirmed
# against real runs -- see the docstring's own real-run history). The
# question now is different: treat GETTING CLOSE to an object as reaching
# it -- stop the approach once within ARRIVAL_DISTANCE_M, call that
# scenario finished, and move on to the next objective (or end, if it was
# the last one), the same way an "approach and stop near the target"
# objective would work in practice, rather than continuing to crash
# through it just to prove a point that's already been proven.
#
# Matches core/config.py's own FOUND_DISTANCE_M (0.80 m) -- the same
# "close enough, call it found/reached" threshold Task 4's own approach
# logic uses -- so this test calls an object "reached" by the same
# standard the rest of the project already uses, not a separately-tuned
# number.
ARRIVAL_DISTANCE_M = config.FOUND_DISTANCE_M

# How close to an object's own registered coordinate counts as "basically
# stopped at/inside it" -- used now only to flag a SUSPICIOUSLY close
# stop (closer than the approach was even aiming for) as a possible real
# collision rather than a clean arrival. Not based on the objects' real
# physical footprints (not available to this script -- OBJECT_POSITIONS is
# just a point, see core/config.py's own comment on it), so this is a
# generous first-pass guess, not a measured object radius.
COLLISION_DISTANCE_M = 0.6

# A single trunk-height jump bigger than this (within one run_fast()
# segment) is flagged by run_fast() itself as "likely impact/stumble" --
# duplicated here only so this script's own verdict text can explain what
# triggered it; the actual detection happens inside run_fast().
MAX_HEIGHT_JUMP_M = 0.15

# Default scenario set: just open_ground (the no-object baseline) and
# red_stop sign (-1.3, 0.0) -- the closest object to spawn, so this stays a
# short, quick default run. green_chair was dropped from the default (it's
# still reachable via --scenario "green_chair", same as every other
# graded object). The rest of core.config.OBJECT_POSITIONS are reachable
# individually via --scenario "<name>", or all at once via --scenario all.
DEFAULT_SCENARIOS = ["open_ground", "red_stop sign"]

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


def _target_before(start_x: float, start_y: float, obj_x: float, obj_y: float,
                    stop_short: float) -> tuple:
    """A point `stop_short` meters BEFORE (obj_x, obj_y), as seen from
    (start_x, start_y) -- i.e. approaching along the same straight line
    but stopping short of the object instead of continuing through it
    (see ARRIVAL_DISTANCE_M's comment for why). run_object_scenario()
    always calls this with (start_x, start_y) = STAGING_POINT (after
    first returning there), so in practice this is "stop stop_short
    meters before the object, as seen from the fixed staging point" --
    kept as a generic start-point function rather than hardcoding
    STAGING_POINT in here, since open_ground has no use for it at all."""
    dx = obj_x - start_x
    dy = obj_y - start_y
    dist = math.hypot(dx, dy)
    if dist <= stop_short:
        # Already within stop_short of the object (or standing on its own
        # coordinate) -- nothing left to approach, stay where we are.
        return start_x, start_y
    ux, uy = dx / dist, dy / dist
    return obj_x - ux * stop_short, obj_y - uy * stop_short


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

    # REVISED after a real run: this fired right after a genuine collision
    # (the return-to-staging leg starting from where the robot was stuck
    # against red_stop_sign, ~0.3 m away) -- every candidate route's FIRST
    # leg starts at (ax,ay), which was already inside SAFE_MARGIN_M of
    # that object before any route was even tried, so no detour could
    # possibly satisfy the margin check. That's expected, not a bug: a
    # route planner can't route AROUND a margin violation that's true at
    # the starting point itself. The direct-line fallback in that case
    # worked fine in practice (the robot simply moved away from the thing
    # it had just hit).
    start_dist_issue = _segment_clears_objects(ax, ay, ax, ay, exclude=exclude)[1]
    if start_dist_issue is not None:
        print(f"  [WARN] _safe_route: the START point is already within "
              f"{SAFE_MARGIN_M:.1f} m of {start_dist_issue!r} (likely just "
              f"collided with or passed close to it) -- no route can plan "
              f"around that, so using the direct line and hoping it moves "
              f"away cleanly.")
    else:
        print(f"  [WARN] _safe_route found no detour that clears every "
              f"other object by {SAFE_MARGIN_M:.1f} m -- falling back to "
              f"the direct line (only checked clear of {exclude!r}). If "
              f"this leg reports 'stuck', it may be a different object "
              f"than the one this scenario names, or the target itself "
              f"may just be close to another object -- nothing a route "
              f"detour alone can fix.")
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
                         arrival_distance: float = ARRIVAL_DISTANCE_M) -> dict:
    """Return to STAGING_POINT first (so the approach below always starts
    from a known, scene-clear position regardless of where the previous
    scenario left the robot -- see the "REVISED after a real run"
    docstring paragraph), then aim run_fast() at a point `arrival_distance`
    meters BEFORE obj_name's own registered position (core.config.
    OBJECT_POSITIONS) -- i.e. approach it and stop once close enough to
    call it reached, rather than continuing through it (see ARRIVAL_
    DISTANCE_M's own comment for why this changed from the original
    overshoot-through-it design).

    If the return-to-staging leg itself doesn't complete cleanly, the
    object approach is skipped rather than run from an unknown position --
    see module docstring. Once this scenario finishes (reached, blocked,
    or skipped), the caller (main()) moves on to the next scenario in the
    list, or ends if this was the last one -- this function itself always
    returns rather than looping or retrying, so "process to the next
    objective" is just main()'s normal scenario loop continuing."""
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
            "reached": False,
        }

    start_pose = staged_pose
    start_height = skills.get_trunk_height()
    target_x, target_y = _target_before(start_pose.x, start_pose.y, obj_x, obj_y,
                                         arrival_distance)

    # exclude=obj_name: the object itself sits just past this leg's target
    # now (arrival_distance short of it), so treat it the same as before --
    # not something to detour around -- and only check clearance from
    # everything else.
    approach_route = _safe_route(start_pose.x, start_pose.y,
                                  target_x, target_y, exclude=obj_name)
    if len(approach_route) > 1:
        print(f"  Direct line toward {obj_name} would pass within "
              f"{SAFE_MARGIN_M:.1f} m of a DIFFERENT object -- detouring "
              f"via {approach_route[:-1]} first.")

    print(f"  Staged cleanly. Now approaching {obj_name}'s own position "
          f"({obj_x}, {obj_y}), stopping {arrival_distance:.2f} m short of "
          f"it (target=({target_x:.2f}, {target_y:.2f})) ===")
    print(f"  Starting at x={start_pose.x:.2f} y={start_pose.y:.2f} "
          f"yaw={start_pose.yaw_deg:.1f} trunk_z={start_height:.3f} m")

    outcome, _ = _run_waypoints(skills, approach_route)

    end_pose = skills.get_robot_pose()
    end_height = skills.get_trunk_height()
    dist_short_of_target = math.hypot(target_x - end_pose.x, target_y - end_pose.y)
    dist_to_object = math.hypot(obj_x - end_pose.x, obj_y - end_pose.y)
    height_delta = end_height - start_height

    # REVISED: ending up near the object is now the GOAL (arrival), not a
    # collision sign -- the target itself was already placed
    # arrival_distance short of it. So "reached" is simply: run_fast()
    # completed its own approach (or got close enough that the remaining
    # gap is explained by arrival_tolerance) AND didn't end up suspiciously
    # closer than the approach was even aiming for (that would mean it
    # pushed past its own stopping point into the object, i.e. a real
    # collision despite the softer target).
    reached = (outcome == "completed" and dist_to_object >= COLLISION_DISTANCE_M)

    reasons = []
    if outcome == "stuck":
        reasons.append(
            f"run_fast() returned 'stuck' -- its own stuck-detector caught "
            f"forward progress stalling out before reaching the approach "
            f"point, {dist_to_object:.2f} m from {obj_name} (aiming to "
            f"stop at {arrival_distance:.2f} m) -- something blocked it "
            f"earlier than planned")
    elif outcome != "completed":
        reasons.append(
            f"run_fast() returned {outcome!r} instead of 'completed' -- it "
            f"did not finish its own approach, {dist_to_object:.2f} m from "
            f"{obj_name} (aiming to stop at {arrival_distance:.2f} m)")
    if dist_to_object < COLLISION_DISTANCE_M:
        reasons.append(
            f"ended only {dist_to_object:.2f} m from {obj_name}'s own "
            f"position -- closer than the {arrival_distance:.2f} m stand-"
            f"off this approach was aiming for, consistent with pushing "
            f"past the intended stopping point and into the object")
    if abs(height_delta) > MAX_HEIGHT_JUMP_M:
        reasons.append(
            f"trunk height moved {height_delta:+.3f} m start-to-end "
            f"(start {start_height:.3f} m -> end {end_height:.3f} m) -- "
            f"check the per-segment [RUN] trace above for which specific "
            f"segment's trunk_z jump run_fast() itself flagged")

    verdict = "REACHED -- treating as finished, moving to next objective" \
        if reached else "NOT REACHED"

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
        "reached": reached,
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
    ap.add_argument("--arrival-distance", type=float, default=ARRIVAL_DISTANCE_M,
                     help=f"how close to each object's own position counts "
                          f"as having reached it -- the approach stops this "
                          f"far short of the object's (x, y) and moves on "
                          f"to the next objective (default "
                          f"{ARRIVAL_DISTANCE_M:.2f}, matching core.config."
                          f"FOUND_DISTANCE_M).")
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
        for i, name in enumerate(scenarios_to_run):
            if name == "open_ground":
                result = run_open_ground_scenario(skills)
            else:
                result = run_object_scenario(skills, name,
                                              arrival_distance=args.arrival_distance)
            results.append(result)
            # "process to the next objective or end": this loop just
            # continuing is that -- each scenario (reached, not reached,
            # or skipped) is final once run_object_scenario() returns, so
            # there's nothing more to do here than announce which way it
            # goes next.
            is_last = (i == len(scenarios_to_run) - 1)
            if is_last:
                print(f"\n({name!r} was the last objective -- finishing up.)")
            else:
                print(f"\n(Moving on to next objective: {scenarios_to_run[i + 1]!r}.)")

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
                status = "REACHED" if r["reached"] else "NOT REACHED"
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
