"""
commands.py — STUDENT B OWNS THIS FILE. Bonus command types.

Commands that only ever flow parser -> CommandQueue -> executor (all inside
dialogue/), so they live here instead of core/schema.py. The queue doesn't
care about the type.
"""

from dataclasses import dataclass


@dataclass
class LookCommand:
    """Answer a question about what the robot currently sees (VLM)."""
    question: str
    kind: str = "look"


# ---------------------------------------------------------------------------
# Task 3 upgrade: programs. The LLM writes a program once; CODE expands and
# runs it (dialogue/executor.py), checking the e-stop flag between steps.
# Bounds (dialogue/limits.py) are enforced by llm_parser's validator.
# ---------------------------------------------------------------------------

@dataclass
class DistanceMoveCommand:
    """Walk until the planar distance travelled (from get_robot_pose)
    reaches |distance_m|, at velocity (vx, vy, wz); distance_m < 0 walks
    the opposite way. Executed closed-loop, with a time cap."""
    vx: float
    vy: float
    wz: float
    distance_m: float
    kind: str = "move_distance"


@dataclass
class RepeatCommand:
    """Run `actions` `times` times (1..limits.MAX_ITER)."""
    times: int
    actions: list
    kind: str = "repeat"


@dataclass
class UntilSeeCommand:
    """Until YOLO reports `object_class` (in `color`, or any colour if ""):
    look, and if it isn't there run `actions`; at most `max_iter` times."""
    object_class: str
    color: str
    actions: list
    max_iter: int
    kind: str = "until_see"


# ---------------------------------------------------------------------------
# Task 3 upgrade: state and repair. The LLM only SELECTS these; the executor
# answers / computes the motion from dialogue/state.py.
# ---------------------------------------------------------------------------

STATUS_TOPICS = ("last_action", "home", "last_reject", "seen", "general")


@dataclass
class StatusCommand:
    """Answer a question about the robot's own state, from the state store."""
    topic: str = "general"
    kind: str = "status"


@dataclass
class UndoCommand:
    """Invert the last motion in the executed-action log."""
    kind: str = "undo"


@dataclass
class ReturnHomeCommand:
    """Turn to face the start, walk there closed-loop, turn to its heading."""
    kind: str = "return_home"
