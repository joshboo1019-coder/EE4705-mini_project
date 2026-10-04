"""
state.py — STUDENT B OWNS THIS FILE. Task 3 upgrade: what the robot knows.

RobotState is written by the executor thread and read by the chat thread
(under a lock):

* home pose — the first pose seen (the executor reads it at start-up),
  and the current pose (updated whenever the executor reads one);
* the executed-action log — what ACTUALLY ran, one record per top-level
  action, with the pose before and after, whether it completed, and
  goto/until_see results. undo and return_home are computed from it;
* objects seen — FROM YOLO ONLY: RecordingPerception wraps the
  PerceptionAPI the executor uses, so every detect() result (navigation's,
  look's, until_see's) is stored as class, colour, confidence, the robot's
  pose and yaw when seen, and time; de-duplicated per colour+class, keeping
  the last sighting (and the first-seen order, for "the first thing you
  saw"). Ground truth (config.OBJECT_POSITIONS) is never read here;
* the last rejection (for "why did you reject that?").

snapshot() is the compact text sent with each LLM call (< ~120 tokens);
answer(topic) is how the `status` action is answered — by code, no LLM.
"""

import math
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

from dialogue import talkback
from dialogue.limits import kind, wrap_deg

UNDOABLE = {"move", "move_distance", "turn", "goto_object", "repeat", "until_see", "return_home"}
NOT_LOGGED = {"chat", "status"}     # answers, not actions


@dataclass
class ActionRecord:
    batch: int
    command: object
    pose_before: object
    pose_after: object
    completed: bool                  # False: failed or e-stopped part-way
    result: object = None            # goto: reached; until_see: (seen, iterations)
    t: float = 0.0
    undone: bool = False
    is_undo: bool = False

    @property
    def kind(self) -> str:
        return kind(self.command)

    @property
    def undoable(self) -> bool:
        return self.kind in UNDOABLE and not self.undone and not self.is_undo

    def words(self, say: bool = False) -> str:
        if self.is_undo:
            undid = getattr(self.command, "_undid", None)
            return f"undo ({talkback.words(undid.command, say=say)})" if undid else "undo"
        w = talkback.words(self.command, say=say)
        if self.kind == "goto_object":
            w += " (reached)" if self.result else " (not reached)"
        if self.kind == "until_see" and isinstance(self.result, tuple):
            w += " (seen)" if self.result[0] else " (not seen)"
        if not self.completed:
            w += " (stopped early)"
        if self.undone:
            w += " (undone)"
        return w


@dataclass
class Sighting:
    class_name: str
    color: str
    conf: float
    x: float
    y: float
    yaw_deg: float
    t_first: float
    t_last: float
    order: int                       # first-seen order, 1 = first

    def name(self) -> str:
        return talkback.target_words(self.class_name, self.color)

    @property
    def clear(self) -> bool:
        """YOLO + colour grounding gave a real colour (not "unknown" / ""),
        i.e. something navigation could be sent to."""
        return bool(self.color) and self.color.lower() not in UNCLEAR_COLORS


UNCLEAR_COLORS = {"unknown", "none", "unclear", "-"}


class RobotState:
    MAX_ACTIONS = 50
    SNAPSHOT_ACTIONS = 3
    SNAPSHOT_SEEN = 6

    def __init__(self, clock: Callable[[], float] = time.time):
        self._lock = threading.RLock()
        self._clock = clock
        self.home = None
        self.pose = None
        self.actions: List[ActionRecord] = []
        self.seen = {}               # (color, class) -> Sighting
        self.last_reject: Optional[Tuple[str, str, Optional[str]]] = None
        self.batch = 0

    # ---------------- writing (executor thread, chat thread for rejects)

    def update_pose(self, pose) -> None:
        if pose is None:
            return
        with self._lock:
            if self.home is None:
                self.home = pose
            self.pose = pose

    def new_batch(self) -> int:
        with self._lock:
            self.batch += 1
            return self.batch

    def record_action(self, rec: ActionRecord) -> None:
        with self._lock:
            rec.t = rec.t or self._clock()
            self.actions.append(rec)
            del self.actions[:-self.MAX_ACTIONS]
            self.update_pose(rec.pose_after)

    def record_detections(self, detections, pose) -> None:
        if not detections or pose is None:
            return
        now = self._clock()
        with self._lock:
            for d in detections:
                key = (d.color, d.class_name)
                s = self.seen.get(key)
                if s is None:
                    self.seen[key] = Sighting(d.class_name, d.color, float(d.conf), pose.x, pose.y,
                                              pose.yaw_deg, now, now, len(self.seen) + 1)
                else:
                    s.conf, s.x, s.y, s.yaw_deg, s.t_last = (float(d.conf), pose.x, pose.y,
                                                             pose.yaw_deg, now)

    def record_reject(self, text: str, reason: str, suggestion: Optional[str]) -> None:
        with self._lock:
            self.last_reject = (text, reason, suggestion)

    # ---------------- reading

    def last_undoable(self) -> Optional[ActionRecord]:
        with self._lock:
            for rec in reversed(self.actions):
                if rec.undoable:
                    return rec
            return None

    def last_batch(self) -> List[ActionRecord]:
        with self._lock:
            if not self.actions:
                return []
            b = self.actions[-1].batch
            return [r for r in self.actions if r.batch == b]

    def from_home(self):
        """(ahead_m, left_m, distance_m, heading_deg) in the home frame, or None."""
        with self._lock:
            home, pose = self.home, self.pose
        if home is None or pose is None:
            return None
        dx, dy = pose.x - home.x, pose.y - home.y
        h = math.radians(home.yaw_deg)
        ahead = dx * math.cos(h) + dy * math.sin(h)
        left = -dx * math.sin(h) + dy * math.cos(h)
        return ahead, left, math.hypot(dx, dy), wrap_deg(pose.yaw_deg - home.yaw_deg)

    def sightings(self) -> List[Sighting]:
        with self._lock:
            return sorted(self.seen.values(), key=lambda s: s.order)

    def snapshot(self) -> str:
        """Compact state for the LLM (one line, < ~120 tokens)."""
        rel = self.from_home()
        if rel is None or rel[2] < 0.1 and abs(rel[3]) < 2:
            pose = "at the start pose"
        else:
            ahead, left, dist, head = rel
            pose = (f"{dist:.1f} m from start ({ahead:+.1f} m ahead, {left:+.1f} m left), "
                    f"heading {head:+.0f} deg vs start")
        with self._lock:
            recent = [r for r in self.actions if r.kind != "estop"][-self.SNAPSHOT_ACTIONS:]
            # Group by command (batch): the most recent command is what a
            # follow-up ("do that again, but slower") refers to. A flat list
            # of the last actions across commands made the LLM repeat all of
            # them (e2e S2, 2026-10-04: "do that again, but slower" after a
            # sidestep came back as walk + turn + sidestep).
            last_b = self.actions[-1].batch if self.actions else None
            cmd_recs = [r for r in self.actions if r.batch == last_b and r.kind != "estop"]
            last_cmd = ", then ".join(r.words() for r in cmd_recs[:4])
            if len(cmd_recs) > 4:
                last_cmd += f" (+{len(cmd_recs) - 4} more steps)"
            earlier = "; ".join(r.words() for r in recent if r.batch != last_b)
            sightings = self.sightings()
            reject = self.last_reject
        if last_cmd:
            last = f"last command: {last_cmd}" + (f" | earlier: {earlier}" if earlier else "")
        else:
            last = "last command: none"
        seen = [s.name() for s in sightings if s.clear]
        unclear = sum(1 for s in sightings if not s.clear)
        seen_txt = (", ".join(seen[:self.SNAPSHOT_SEEN]) + (", ..." if len(seen) > self.SNAPSHOT_SEEN else "")
                    if seen else "nothing yet")
        if unclear:
            seen_txt += f" (+{unclear} detection{'s' if unclear > 1 else ''} without a clear colour)"
        out = (f"STATE: {pose} | {last} | "
               f"camera has seen (first to last): {seen_txt}")
        if reject:
            out += f" | last rejected: \"{reject[0][:40]}\" ({reject[1]})"
        return out

    # ---------------- status answers (code, no LLM)

    def answer(self, topic: str) -> str:
        if topic == "last_action":
            return self._answer_last_action()
        if topic == "home":
            return self._answer_home()
        if topic == "last_reject":
            return self._answer_reject()
        if topic == "seen":
            return self._answer_seen()
        return f"{self._answer_home()} {self._answer_seen()}"

    def _answer_last_action(self) -> str:
        batch = self.last_batch()
        if not batch:
            return "I haven't done anything yet."
        steps = ", then ".join(r.words(say=True) for r in batch)
        p0, p1 = batch[0].pose_before, batch[-1].pose_after
        moved = ""
        if p0 is not None and p1 is not None:
            d = math.hypot(p1.x - p0.x, p1.y - p0.y)
            turn = wrap_deg(p1.yaw_deg - p0.yaw_deg)
            bits = ([f"moved {d:.1f} m"] if d >= 0.05 else []) + \
                   ([f"turned {abs(turn):.0f}° {'left' if turn > 0 else 'right'}"] if abs(turn) >= 2 else [])
            moved = f" Overall I {' and '.join(bits)}." if bits else " I ended where I began."
        return f"I just did this: {steps}.{moved}"

    def _answer_home(self) -> str:
        rel = self.from_home()
        if rel is None:
            return "I don't know where I started."
        ahead, left, dist, head = rel
        facing = ("facing the way I started" if abs(head) < 2 else
                  "facing the opposite way from when I started" if abs(head) > 178 else
                  f"facing {abs(head):.0f}° {'left' if head > 0 else 'right'} of my starting direction")
        if dist < 0.1:
            return f"I'm at my starting point, {facing}."
        return (f"I'm {dist:.1f} m from where I started ({abs(ahead):.1f} m "
                f"{'ahead' if ahead >= 0 else 'behind'}, {abs(left):.1f} m to the "
                f"{'left' if left >= 0 else 'right'}), {facing}.")

    def _answer_reject(self) -> str:
        with self._lock:
            rej = self.last_reject
        if rej is None:
            return "I haven't rejected anything yet."
        text, reason, suggestion = rej
        out = f'I rejected "{text}" because {talkback.reason_words(reason)}.'
        if suggestion:
            out += f' I suggested "{suggestion}" instead.'
        return out

    def _answer_seen(self) -> str:
        """Objects with a clear colour first (what navigation can go to);
        detections YOLO couldn't colour (often false positives, e.g. an
        "unknown bench") only as a count with their classes."""
        all_seen = self.sightings()
        seen = [s for s in all_seen if s.clear]
        other = [s for s in all_seen if not s.clear]
        if not all_seen:
            return "My camera hasn't recognised any objects yet."
        now = self._clock()
        items = []
        for k, s in enumerate(seen):
            tag = " (first)" if k == 0 and len(seen) > 1 else ""
            items.append(f"the {s.name()}{tag}, last seen {now - s.t_last:.0f} s ago "
                         f"at heading {s.yaw_deg:+.0f}°")
        rest = ""
        if other:
            kinds = ", ".join(dict.fromkeys(s.class_name for s in other))
            rest = (f"plus {len(other)} other detection{'s' if len(other) > 1 else ''} "
                    f"without a clear colour ({kinds})")
        if not seen:
            return f"I haven't seen any object clearly yet, {rest}."
        out = f"I've seen {len(seen)} object{'s' if len(seen) > 1 else ''}: " + "; ".join(items)
        return out + (f"; {rest}." if rest else ".")


class RecordingPerception:
    """PerceptionAPI pass-through that records every detect() result in a
    RobotState (with the robot pose from pose_fn). Everything else —
    including the optional hooks navigation looks up (remember_target,
    recover_target, clear_target_history) — is delegated unchanged."""

    def __init__(self, inner, state: RobotState, pose_fn: Callable):
        self._inner = inner
        self._state = state
        self._pose_fn = pose_fn

    def detect(self, frame, *args, **kwargs):
        detections = self._inner.detect(frame, *args, **kwargs)
        try:
            self._state.record_detections(detections, self._pose_fn())
        except Exception:      # bookkeeping must never break perception
            pass
        return detections

    def __getattr__(self, name):
        return getattr(self._inner, name)
