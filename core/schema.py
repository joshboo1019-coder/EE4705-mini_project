"""
schema.py — Shared data contracts for MiniLab 1.3.

ALL THREE STUDENTS IMPORT FROM THIS FILE AND NEVER EDIT IT ALONE.
If you need a new field, propose it to the group first — changing this file
silently is the #1 way integration breaks the night before the deadline.

Owner: whole group, frozen after a 10-minute kickoff call.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union
import queue
import threading

# Bump on any semantic change to the dataclasses/CommandQueue below (new
# required field, removed field, changed meaning) and mention it in
# docs/DECISIONS.md. Purely additive optional fields don't need a bump.
CONTRACT_VERSION = 1

# ---------------------------------------------------------------------------
# Commands produced by Student B's LLM parser (Task 3),
# consumed by the executor (Task 3) which calls Student A's skills (Task 2)
# and Student C's navigation (Task 4).
# ---------------------------------------------------------------------------


@dataclass
class MoveCommand:
    vx: float            # [-1, 1] forward positive
    vy: float            # [-1, 1] left positive
    wz: float            # [-1, 1] turn-left (CCW) positive
    duration: float       # seconds
    kind: str = "move"


@dataclass
class TurnCommand:
    angle_deg: float      # positive = left (CCW)
    kind: str = "turn"


@dataclass
class GotoObjectCommand:
    object_class: str     # COCO class name, e.g. "chair"
    color: str             # e.g. "green"
    kind: str = "goto_object"


@dataclass
class StopCommand:
    kind: str = "stop"


@dataclass
class ChatCommand:
    reply: str
    kind: str = "chat"


Command = Union[MoveCommand, TurnCommand, GotoObjectCommand, StopCommand, ChatCommand]


@dataclass
class ParseResult:
    accepted: bool
    commands: List[Command] = field(default_factory=list)
    reject_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Perception types produced by Student C (Task 4)
# ---------------------------------------------------------------------------


@dataclass
class Detection:
    class_name: str
    color: str
    conf: float
    bbox: tuple  # (x1, y1, x2, y2) pixel coords


@dataclass
class RobotPose:
    x: float
    y: float
    yaw_deg: float


# ---------------------------------------------------------------------------
# Thread-safe command queue shared between the chat thread (Student B)
# and the main simulation loop (ALL). This is what lets the sim keep
# stepping physics while the user is typing / the LLM call is in flight.
# ---------------------------------------------------------------------------


class CommandQueue:
    """FIFO queue of parsed commands. The chat thread pushes; the executor
    pops and runs one command at a time."""

    def __init__(self):
        self._q = queue.Queue()

    def push_many(self, commands: List[Command]) -> None:
        for c in commands:
            self._q.put(c)

    def pop(self, timeout: Optional[float] = None) -> Optional[Command]:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self) -> None:
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def empty(self) -> bool:
        return self._q.empty()
