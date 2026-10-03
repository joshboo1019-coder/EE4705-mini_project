"""
limits.py — STUDENT B OWNS THIS FILE. Safety bounds of the Task 3 parser.

One place for the numbers the validator (llm_parser._to_parse_result)
enforces and the talk-back (talkback.py) quotes back to the user, so the
"I could walk forward for 30 seconds instead" suggestion can never drift
from what the validator actually accepts.
"""

import math

from core import config

MAX_SPEED = 1.0                                        # |vx|, |vy|, |wz|
MAX_MOVE_S = getattr(config, "LLM_MAX_DURATION_S", 30.0)  # one move
MAX_PROGRAM_S = 60.0     # estimated motion time of one utterance, loops multiplied out
MAX_ITER = 8             # repeat.times and until_see.max_iter
MAX_NESTING = 2          # a program inside a program is depth 2; deeper is rejected
TURN_RATE_DPS = 45.0     # nominal in-place turn rate used for the time estimate
NORMAL_SPEED = 0.8       # the prompt's "normal walking speed"
MIN_TRANSLATION = 0.05   # |(vx, vy)| below this cannot cover a distance


def kind(c) -> str:
    return getattr(c, "kind", "")


def program_seconds(commands) -> float:
    """Estimated motion time of validated commands: timed moves count their
    duration, distance moves |distance_m| / |(vx, vy)| (the v4 convention
    speed in m/s ~= |v|), turns |angle| / TURN_RATE_DPS, repeats times x
    body, until_see max_iter x body. goto_object and look are NOT counted:
    navigation has its own timeout (config.APPROACH_TIMEOUT_S) and look does
    not move."""
    total = 0.0
    for c in commands:
        k = kind(c)
        if k == "move":
            total += c.duration
        elif k == "move_distance":
            total += distance_seconds(c.vx, c.vy, c.distance_m)
        elif k == "turn":
            total += abs(c.angle_deg) / TURN_RATE_DPS
        elif k == "repeat":
            total += c.times * program_seconds(c.actions)
        elif k == "until_see":
            total += c.max_iter * program_seconds(c.actions)
    return total


def distance_seconds(vx: float, vy: float, distance_m: float) -> float:
    speed = math.hypot(vx, vy)
    return abs(distance_m) / speed if speed >= MIN_TRANSLATION else float("inf")


def wrap_deg(a: float) -> float:
    """Angle in (-180, 180]."""
    a = (a + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a
