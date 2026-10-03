"""
talkback.py — STUDENT B OWNS THIS FILE. Task 3 upgrade: the robot talks back.

Everything here is TEMPLATES over data the system already has (the parsed
commands, the validator's bounds, the executor's pose trace). No LLM call
is made for talk-back; the only LLM-sourced text is the optional English
`suggestion` a v5 reject carries, which is only ever SAID, never executed.

Lines produced (all of them new; the existing [CMD]/[EXEC]/[DONE]/... lines
are untouched):

    [PLAN] walk forward 3 s at 0.8, then turn left 180°     right after [CMD]
    Robot: Done: moved 2.3 m, net turn 180° left.            right after [DONE]
    Robot: I only take commands in English. Did you mean "..."?
    Robot: The longest single move is 30 s; I could walk forward for 30 seconds instead.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from dialogue import limits
from dialogue.limits import kind, wrap_deg

# ---------------------------------------------------------------------------
# Commands in plain words
# ---------------------------------------------------------------------------


def _g(x: float) -> str:
    return f"{x:g}"


def _n(x: float, unit: str) -> str:
    """'1 second', '2.5 seconds'."""
    return f"{_g(x)} {unit}{'' if x == 1 else 's'}"


def _move_verb(vx: float, vy: float, wz: float) -> str:
    fwd = "forward" if vx >= 0.05 else "backward" if vx <= -0.05 else ""
    side = "left" if vy >= 0.05 else "right" if vy <= -0.05 else ""
    if fwd and side:
        verb = f"walk {fwd}-{side}"
    elif fwd:
        verb = f"walk {fwd}"
    elif side:
        verb = f"sidestep {side}"
    elif abs(wz) >= 0.05:
        return f"turn {'left' if wz > 0 else 'right'} on the spot"
    else:
        return "stand still"
    if abs(wz) >= 0.05:
        verb += f" while turning {'left' if wz > 0 else 'right'}"
    return verb


def _speed(vx: float, vy: float, wz: float) -> float:
    s = math.hypot(vx, vy)
    return round(s if s >= 0.05 else abs(wz), 2)


def _adverb(vx: float, vy: float, wz: float) -> str:
    sp = _speed(vx, vy, wz)
    return " at full speed" if sp >= 0.95 else " slowly" if sp <= 0.4 else ""


def target_words(object_class: str, color: str) -> str:
    return f"{color} {object_class}".strip()


def words(c, say: bool = False) -> str:
    """One command in plain words. say=False: compact [PLAN] style
    ("walk forward 3 s at 0.8"); say=True: an English instruction a user
    could type ("walk forward for 3 seconds")."""
    k = kind(c)
    if k == "move":
        verb = _move_verb(c.vx, c.vy, c.wz)
        if say:
            return f"{verb}{_adverb(c.vx, c.vy, c.wz)} for {_n(c.duration, 'second')}"
        return f"{verb} {_g(c.duration)} s at {_g(_speed(c.vx, c.vy, c.wz))}"
    if k == "move_distance":
        s = -1.0 if c.distance_m < 0 else 1.0
        verb = _move_verb(c.vx * s, c.vy * s, c.wz)
        d = abs(c.distance_m)
        if say:
            return f"{verb}{_adverb(c.vx, c.vy, c.wz)} {_n(round(d, 2), 'metre')}"
        return f"{verb} {_g(round(d, 2))} m at {_g(_speed(c.vx, c.vy, c.wz))}"
    if k == "turn":
        a = c.angle_deg
        side = "left" if a >= 0 else "right"
        return f"turn {side} {_n(abs(a), 'degree')}" if say else f"turn {side} {_g(abs(a))}°"
    if k == "goto_object":
        return f"go to the {target_words(c.object_class, c.color)}"
    if k == "stop":
        return "stop"
    if k == "chat":
        return "reply"
    if k == "look":
        return f'look and answer "{c.question}"'
    if k == "repeat":
        body = join(c.actions, say)
        return f"{body}, {c.times} times" if say else f"repeat {c.times}x ({body})"
    if k == "until_see":
        body = join(c.actions, say)
        tgt = target_words(c.object_class, c.color)
        if say:
            return f"keep doing this until you see the {tgt}: {body}"
        return f"until I see the {tgt}, up to {c.max_iter}x ({body})"
    if k == "status":
        return f"report {STATUS_WORDS.get(c.topic, 'my state')}"
    if k == "undo":
        return "undo my last motion"
    if k == "return_home":
        return "go back to where I started"
    return str(c)


STATUS_WORDS = {"last_action": "what I just did", "home": "where I am relative to the start",
                "last_reject": "why I rejected the last request", "seen": "what I have seen",
                "general": "my state"}


def join(commands, say: bool = False) -> str:
    return ", then ".join(words(c, say) for c in commands)


MOTION_KINDS = {"move", "move_distance", "turn", "goto_object", "stop", "repeat", "until_see",
                "undo", "return_home"}


def plan_line(commands) -> Optional[str]:
    """The [PLAN] line for a parsed batch: any batch with a move (timed,
    distance, or inside a program) or with two or more actions. None
    otherwise. undo / return_home get a second, concrete [PLAN] from the
    executor when they run (computed from the action log / home pose)."""
    kinds = {kind(c) for c in commands}
    if len(commands) >= 2 or kinds & {"move", "move_distance", "repeat", "until_see"}:
        return f"[PLAN] {join(commands)}"
    return None     # a lone undo / return_home: the executor prints the computed [PLAN]


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------

def _bound_sentence(reason: str) -> str:
    what = reason.split(":", 1)[1].lower() if ":" in reason else reason.lower()
    if reason.startswith("program_too_long"):
        secs = what.rstrip("s")
        return (f"One request can take at most {_g(limits.MAX_PROGRAM_S)} s of motion"
                + (f" and that one needs about {secs} s" if secs.replace(".", "").isdigit() else ""))
    if reason.startswith("too_many_iterations") or any(w in what for w in ("iteration", "times", "repeat")):
        return f"I can repeat something at most {limits.MAX_ITER} times"
    if reason.startswith("nesting_too_deep"):
        return f"I can only nest loops {limits.MAX_NESTING} deep"
    if any(w in what for w in ("vx", "vy", "wz", "speed", "fast", "veloc")):
        return f"My top speed setting is {_g(limits.MAX_SPEED)}"
    if any(w in what for w in ("distance", "meter", "metre", "km", "mile", "far")):
        far = limits.MAX_MOVE_S * limits.NORMAL_SPEED
        return (f"The longest single move is {_g(limits.MAX_MOVE_S)} s, "
                f"about {far:.0f} m at walking speed")
    if any(w in what for w in ("duration", "time", "second", "minute", "hour", "long", "angle")):
        return f"The longest single move is {_g(limits.MAX_MOVE_S)} s"
    return (f"That is beyond my limits (one move up to {_g(limits.MAX_MOVE_S)} s, "
            f"speed up to {_g(limits.MAX_SPEED)})")


def is_out_of_range(reason: str, suggestion: Optional[str]) -> bool:
    if reason.startswith(("out_of_range", "program_too_long", "too_many_iterations",
                          "nesting_too_deep")):
        return True
    # the validator's numeric bounds keep their old reason (invalid_field:<f>)
    # and attach a clamped suggestion only when the value was a finite
    # number outside the bounds.
    return reason.startswith("invalid_field:") and bool(suggestion)


_REASON_WORDS = {
    "non-English": "it wasn't in English",
    "empty": "I didn't hear a command",
    "malformed_json": "my language model returned something I couldn't read",
}


def reason_words(reason: str) -> str:
    if reason in _REASON_WORDS:
        return _REASON_WORDS[reason]
    head, _, what = reason.partition(":")
    what = what.replace("_", " ")
    if head == "impossible":
        return f"it is physically impossible for me ({what})"
    if head == "unsafe":
        return f"it isn't safe ({what})"
    if head in ("out_of_range", "program_too_long", "too_many_iterations", "nesting_too_deep"):
        return _bound_sentence(reason)[0].lower() + _bound_sentence(reason)[1:]
    if head == "llm_error":
        return f"my language service failed ({what})"
    if head in ("invalid_field", "unknown_action", "unknown_class", "invalid_in_program"):
        return f"the plan had an invalid {head.split('_')[-1]} ({what})"
    return reason.replace("_", " ")


def reject_reply(reason: Optional[str], suggestion: Optional[str] = None) -> Optional[str]:
    """The `Robot: ...` sentence after `[CMD] rejected reason=...`, or None
    (an empty input gets no reply)."""
    reason = reason or "unspecified"
    if reason == "empty":
        return None
    if reason == "non-English":
        if suggestion:
            return f'I only take commands in English. Did you mean "{suggestion}"?'
        return "I only take commands in English. Please say it again in English."
    if is_out_of_range(reason, suggestion):
        bound = _bound_sentence(reason)
        if suggestion:
            return f"{bound}; I could {suggestion} instead."
        return f"{bound}. Could you ask for something smaller?"
    head, _, what = reason.partition(":")
    if head == "impossible":
        return f"I can't do that: it is physically impossible for a robot dog ({what.replace('_', ' ')})."
    if head == "unsafe":
        return "I won't do that; it isn't safe."
    if head == "llm_error":
        return "Sorry, my language service didn't answer. Please try again."
    if any(w in reason.lower() for w in ("ambig", "unclear", "vague")):
        return "Sorry, I'm not sure what you mean. Could you say exactly where or what?"
    # any other model-made reason: its free-text suggestion is not shown (it
    # can be a question or exceed a limit), only a request to rephrase
    return "Sorry, I couldn't turn that into a safe command. Could you rephrase it?"


# ---------------------------------------------------------------------------
# After [DONE]
# ---------------------------------------------------------------------------

@dataclass
class BatchTrace:
    """What actually happened in one [EXEC]...[DONE] batch."""
    kinds: List[str]
    pose_before: Optional[object] = None
    pose_after: Optional[object] = None
    done: int = 0
    failed: Optional[Tuple[int, str]] = None        # (action index, short error)
    aborted_at: Optional[int] = None                 # action index the e-stop hit
    goals: List[Tuple[str, bool]] = field(default_factory=list)       # goto: (target, reached)
    sightings: List[Tuple[str, bool, int]] = field(default_factory=list)  # until_see: (target, seen, iters)
    skipped: int = 0                                 # actions skipped after a failed until_see
    notes: List[str] = field(default_factory=list)   # e.g. "nothing to undo"


def _motion_phrase(t: BatchTrace) -> Optional[str]:
    p0, p1 = t.pose_before, t.pose_after
    if p0 is None or p1 is None:
        return None
    dist = math.hypot(p1.x - p0.x, p1.y - p0.y)
    turn = wrap_deg(p1.yaw_deg - p0.yaw_deg)
    parts = []
    if dist >= 0.05:
        parts.append(f"moved {dist:.1f} m")
    if abs(turn) >= 2.0:
        parts.append(f"net turn {abs(turn):.0f}° {'left' if turn > 0 else 'right'}")
    return ", ".join(parts) if parts else "no net change in position"


def summary(t: BatchTrace) -> Optional[str]:
    """One sentence after [DONE] for a batch that moved (or tried to), or
    None for a pure chat / look / status batch (those already answered)."""
    if not (set(t.kinds) & MOTION_KINDS) and t.failed is None and t.aborted_at is None:
        return None
    if set(t.kinds) == {"stop"} and t.failed is None:
        return "Stopped."
    n = len(t.kinds)
    clauses = []
    if t.aborted_at is not None:
        clauses.append(f"Emergency stop: I halted during step {t.aborted_at} of {n}")
    elif t.failed is not None:
        clauses.append(f"Step {t.failed[0]} of {n} failed ({t.failed[1]}), so I stopped there")
    elif t.skipped:
        clauses.append(f"I skipped the last {t.skipped} step{'s' if t.skipped > 1 else ''}")
    else:
        clauses.append("Done")
    for target, seen, iters in t.sightings:
        if seen:
            clauses.append(f"saw the {target} straight away" if iters == 0 else
                           f"saw the {target} after {iters} tr{'y' if iters == 1 else 'ies'}")
        else:
            clauses.append(f"never saw the {target} ({iters} tries)")
    if len(t.goals) == 1:
        target, ok = t.goals[0]
        clauses.append(f"reached the {target}" if ok else f"did not reach the {target}")
    elif t.goals:
        reached = sum(ok for _, ok in t.goals)
        missed = [g for g, ok in t.goals if not ok]
        clauses.append(f"reached {reached} of {len(t.goals)} goals"
                       + (f" (missed the {', the '.join(missed)})" if missed else ""))
    clauses += t.notes
    motion = _motion_phrase(t)
    if motion:
        clauses.append(motion)
    first, rest = clauses[0], clauses[1:]
    sep = ": " if first == "Done" else "; "
    return first + (sep + "; ".join(rest) if rest else "") + "."
