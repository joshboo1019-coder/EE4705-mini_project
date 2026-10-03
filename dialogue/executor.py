"""
executor.py — STUDENT B OWNS THIS FILE. Part of Task 3 (60%).

Pops commands off schema.CommandQueue and runs them in order via the
SkillsAPI (Student A) and navigation.goto_object (Student C). This is the
one place where all three tasks meet — but note it only ever calls the
*interfaces*, so it can be fully tested with skills_mock + perception_mock
before Task 2/4 are finished (tests/test_parser_with_mock.py does this).

Upgrade (Task 3 programs): the executor is also the INTERPRETER for the
programs the parser accepted (repeat, until_see, closed-loop distance
moves). The LLM is never called here: a program is expanded and run by
code, within the bounds the validator already checked (dialogue/limits.py).

Emergency stop: the chat thread's stop fast path (chat_interface.py) calls
emergency_stop() from ITS thread while this one may be mid-program. That
bumps an e-stop counter, calls skills.stop() and clears the queue. Every
batch remembers the counter value it started under; once they differ the
batch is aborted:
  * between steps and between loop iterations (checked explicitly), and
  * inside a step: every skills.move()/turn() this executor or navigation
    issues goes through _AbortableSkills, which refuses to start a new
    motion after the e-stop. So a closed-loop distance walk (0.5 s slices)
    or a goto_object search ends at its next motion call.
skills.stop() zeroes the velocity command at once, so a timed move that is
already running stops moving immediately (its call still returns at its
original end time); a closed-loop turn() already in progress runs to its
end (RealSkills.turn re-commands wz every 20 ms), and then nothing else
starts. The counter is never reset, so a later command runs normally.
"""

import math
import threading
import time
from typing import Callable

from core.interfaces import SkillsAPI, PerceptionAPI
from core.schema import (
    CommandQueue, MoveCommand, TurnCommand, GotoObjectCommand,
    StopCommand, ChatCommand,
)
from perception import navigation
from dialogue import limits, runtime, talkback, vlm
from dialogue.commands import (
    LookCommand, DistanceMoveCommand, RepeatCommand, UntilSeeCommand,
)
from dialogue.limits import kind


class ExecutionAborted(Exception):
    """The e-stop fired; raised at the next step boundary / motion call."""


class _AbortableSkills:
    """SkillsAPI pass-through whose move() and turn() refuse to START once
    the e-stop has fired for the running batch. Everything else (stop,
    pose, camera, and any optional/private attribute navigation looks up,
    e.g. get_trunk_height or _model) is delegated unchanged."""

    def __init__(self, inner: SkillsAPI, aborted: Callable[[], bool]):
        self._inner = inner
        self._aborted = aborted

    def move(self, vx: float, vy: float, wz: float, duration: float) -> None:
        if self._aborted():
            raise ExecutionAborted()
        return self._inner.move(vx, vy, wz, duration)

    def turn(self, angle_deg: float) -> None:
        if self._aborted():
            raise ExecutionAborted()
        return self._inner.turn(angle_deg)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class CommandExecutor:
    # until_see: let the gait settle and a fresh frame render after a motion
    UNTIL_SETTLE_S = 0.3
    # closed-loop distance walk: slice length, arrival tolerance, stall check
    DIST_STEP_S = 0.5
    DIST_TOL_M = 0.03
    DIST_STALL_WINDOW_S = 2.0
    DIST_STALL_MIN_M = 0.05
    DIST_TIME_FACTOR = 4.0   # time cap = factor x nominal (|d| / |v|) + 2 s, <= MAX_PROGRAM_S

    def __init__(self, skills: SkillsAPI, perception: PerceptionAPI,
                 queue: CommandQueue,
                 goto_object_fn: Callable = navigation.goto_object,
                 vlm_fn: Callable = vlm.ask,
                 save_frame_fn: Callable = vlm.save_frame):
        self.skills = skills
        self.perception = perception
        self.queue = queue
        self.goto_object_fn = goto_object_fn
        self.vlm_fn = vlm_fn
        self.save_frame_fn = save_frame_fn
        self._estop_lock = threading.Lock()
        self._estop_count = 0
        self._batch_estop = 0       # _estop_count when the running batch started
        self._busy = False
        self._motion = _AbortableSkills(skills, self._aborted)
        runtime.bind(queue, self)

    # ------------------------------------------------------------------
    # e-stop (called from the chat thread)
    # ------------------------------------------------------------------

    def emergency_stop(self) -> bool:
        """Abort flag, skills.stop(), clear the queue — in that order.
        Thread-safe; returns True if a batch was running."""
        with self._estop_lock:
            self._estop_count += 1
        try:
            self.skills.stop()
        except Exception as e:
            print(f"[ESTOP] skills.stop() failed reason={_short_error(e)}")
        self.queue.clear()
        return self._busy

    def _aborted(self) -> bool:
        return self._estop_count != self._batch_estop

    def _check_abort(self) -> None:
        if self._aborted():
            raise ExecutionAborted()

    # ------------------------------------------------------------------
    # batches
    # ------------------------------------------------------------------

    def run_forever(self, poll_timeout: float = 0.2) -> None:
        """Call this from the main thread's loop (not the chat thread) so
        the simulation keeps stepping while it also executes commands."""
        while True:
            estop = self._estop_count       # read BEFORE pop: an e-stop during
            cmd = self.queue.pop(timeout=poll_timeout)   # the pop aborts what it returns
            if cmd is not None:
                self._run_batch_starting_with(cmd, _estop=estop)

    def _run_batch_starting_with(self, first_cmd, _estop=None) -> None:
        """Runs `first_cmd` and then drains any remaining queued commands
        from the SAME parsed utterance as one [EXEC]...[DONE] sequence."""
        self._batch_estop = self._estop_count if _estop is None else _estop
        self._busy = True
        try:
            self._run_batch(first_cmd)
        finally:
            self._busy = False

    def _run_batch(self, first_cmd) -> None:
        batch = [first_cmd]
        while not self.queue.empty():
            nxt = self.queue.pop(timeout=0.0)
            if nxt is None:
                break
            batch.append(nxt)

        t0 = time.time()
        n = len(batch)
        done = 0
        trace = talkback.BatchTrace(kinds=[kind(c) for c in batch], pose_before=self._pose())
        # Two or more goto_object actions in one utterance form a multi-goal
        # mission: each goal is reported, a goal that isn't reached is
        # skipped (the robot goes on to the next one), and a [MULTI] summary
        # closes the batch.
        n_goals = sum(isinstance(c, GotoObjectCommand) for c in batch)
        mission = [] if n_goals >= 2 else None
        for i, cmd in enumerate(batch, start=1):
            # This runs on the main thread: a skill or navigation error must
            # not kill the program, so it ends this batch and nothing more.
            try:
                self._check_abort()
                reached = self._exec_one(cmd, i, n)
            except ExecutionAborted:
                print(f"[EXEC] action={i}/{n} aborted reason=emergency_stop")
                trace.aborted_at = i
                break
            except Exception as e:
                print(f"[EXEC] action={i}/{n} failed reason={_short_error(e)}")
                self._safe_stop()
                trace.failed = (i, _short_error(e, limit=40))
                break
            done += 1
            if isinstance(cmd, GotoObjectCommand):
                trace.goals.append((_target(cmd), bool(reached)))
            if mission is not None and isinstance(cmd, GotoObjectCommand):
                mission.append((cmd, bool(reached)))
                print(f"[GOAL] {len(mission)}/{n_goals} {_target(cmd)} "
                      f"status={'REACHED' if reached else 'NOT_REACHED'} "
                      f"t={time.time() - t0:.1f} s")
            if isinstance(cmd, UntilSeeCommand):
                seen, iters = reached
                trace.sightings.append((_target(cmd), seen, iters))
                if not seen and i < n:
                    # "until you see X, then ..." — the rest depended on X
                    trace.skipped = n - i
                    print(f"[EXEC] until_see target not seen; skipping "
                          f"{n - i} remaining action(s)")
                    break
        elapsed = time.time() - t0
        if mission is not None:
            print(_mission_summary(mission, n_goals, elapsed))
        print(f"[DONE] actions={done} t={elapsed:.1f} s")
        trace.done = done
        trace.pose_after = self._pose()
        line = talkback.summary(trace)
        if line:
            print(f"Robot: {line}")

    def _pose(self):
        """Pose for the talk-back trace; None if the skills can't say."""
        try:
            return self.skills.get_robot_pose()
        except Exception:
            return None

    def _look(self, question: str) -> None:
        """Visual QA on ONE frame: YOLO's [DETECT] lines and the VLM answer
        come from the same image, so they can be compared."""
        frame = self.skills.get_camera_frame()
        path = self.save_frame_fn(frame)
        try:
            if not self.perception.detect(frame):    # detect() prints [DETECT] lines
                print("[DETECT] none")
        except Exception as e:   # YOLO trouble shouldn't stop the VLM answer
            print(f"[DETECT] failed reason={_short_error(e)}")
        ans = self.vlm_fn(frame, question)
        print(f"[VLM] model={ans.model} t={ans.latency_s:.2f} s "
              f"tokens={ans.tokens_in}/{ans.tokens_out} frame={path}")
        print(f"Robot: {ans.answer}")

    def _safe_stop(self) -> None:
        try:
            self.skills.stop()
        except Exception as e:
            print(f"[EXEC] stop after failure also failed reason={_short_error(e)}")

    def _exec_one(self, cmd, i: int, n: int):
        """Runs one command; returns goto_object's result (True = reached),
        or (seen, iterations) for until_see. Steps inside a program are run
        through here too and log with their top-level action number."""
        if isinstance(cmd, MoveCommand):
            print(f"[EXEC] action={i}/{n} move vx={cmd.vx} vy={cmd.vy} "
                  f"wz={cmd.wz} t={cmd.duration} s")
            self._motion.move(cmd.vx, cmd.vy, cmd.wz, cmd.duration)
        elif isinstance(cmd, TurnCommand):
            print(f"[EXEC] action={i}/{n} turn angle={cmd.angle_deg} deg")
            self._motion.turn(cmd.angle_deg)
        elif isinstance(cmd, GotoObjectCommand):
            print(f"[EXEC] action={i}/{n} goto_object class={cmd.object_class} "
                  f"color={cmd.color}")
            return self.goto_object_fn(cmd.object_class, cmd.color,
                                        self._motion, self.perception)
        elif isinstance(cmd, StopCommand):
            print(f"[EXEC] action={i}/{n} stop")
            self.skills.stop()
            self.queue.clear()
        elif isinstance(cmd, ChatCommand):
            print(f"Robot: {cmd.reply}")
        elif isinstance(cmd, LookCommand):
            print(f'[EXEC] action={i}/{n} look question="{cmd.question}"')
            self._look(cmd.question)
        elif isinstance(cmd, DistanceMoveCommand):
            print(f"[EXEC] action={i}/{n} move vx={cmd.vx} vy={cmd.vy} "
                  f"wz={cmd.wz} distance={cmd.distance_m} m")
            self._walk_distance(cmd.vx, cmd.vy, cmd.wz, cmd.distance_m)
        elif isinstance(cmd, RepeatCommand):
            print(f"[EXEC] action={i}/{n} repeat times={cmd.times} steps={len(cmd.actions)}")
            for k in range(1, cmd.times + 1):
                self._check_abort()
                print(f"[REPEAT] iteration={k}/{cmd.times}")
                for c in cmd.actions:
                    self._check_abort()
                    self._exec_one(c, i, n)
        elif isinstance(cmd, UntilSeeCommand):
            return self._until_see(cmd, i, n)
        else:
            print(f"[EXEC] action={i}/{n} unknown command skipped: {cmd}")

    # ------------------------------------------------------------------
    # program steps
    # ------------------------------------------------------------------

    def _until_see(self, cmd: UntilSeeCommand, i: int, n: int):
        """Look (YOLO, one frame); if the target isn't there run the body;
        at most max_iter bodies, then one last look. Returns (seen, bodies run)."""
        print(f"[EXEC] action={i}/{n} until_see class={cmd.object_class} "
              f"color={cmd.color or '-'} max_iter={cmd.max_iter}")
        for k in range(cmd.max_iter + 1):
            self._check_abort()
            if k:
                time.sleep(self.UNTIL_SETTLE_S)
            hit = self._sees(cmd.object_class, cmd.color)
            if hit is not None:
                print(f"[UNTIL] seen class={hit.class_name} color={hit.color} "
                      f"conf={hit.conf:.2f} after {k} iteration(s)")
                return True, k
            if k == cmd.max_iter:
                break
            print(f"[UNTIL] iteration={k + 1}/{cmd.max_iter} target not seen yet")
            for c in cmd.actions:
                self._check_abort()
                self._exec_one(c, i, n)
        print(f"[UNTIL] not seen after {cmd.max_iter} iteration(s)")
        return False, cmd.max_iter

    def _sees(self, object_class: str, color: str):
        frame = self.skills.get_camera_frame()
        for d in self.perception.detect(frame) or []:    # detect() prints [DETECT]
            if d.class_name == object_class and (not color or d.color == color):
                return d
        return None

    def _walk_distance(self, vx: float, vy: float, wz: float, distance_m: float) -> float:
        """Closed-loop on get_robot_pose(): walk in slices of <= DIST_STEP_S
        until the planar distance from the start reaches |distance_m| (minus
        DIST_TOL_M), the time cap runs out, or progress stalls (blocked).
        Prints [MOVE] target=<m> m final_error=<m> m and returns the
        distance travelled."""
        s = -1.0 if distance_m < 0 else 1.0
        vx, vy = vx * s, vy * s
        target = abs(distance_m)
        speed = math.hypot(vx, vy)
        cap = min(limits.MAX_PROGRAM_S, self.DIST_TIME_FACTOR * target / speed + 2.0)
        start = self.skills.get_robot_pose()
        travelled, elapsed, log = 0.0, 0.0, [(0.0, 0.0)]
        status = ""
        while target - travelled > self.DIST_TOL_M:
            if elapsed >= cap:
                status = " status=timeout"
                break
            dt = max(0.1, min(self.DIST_STEP_S, (target - travelled) / speed))
            self._motion.move(vx, vy, wz, dt)
            elapsed += dt
            p = self.skills.get_robot_pose()
            travelled = math.hypot(p.x - start.x, p.y - start.y)
            log.append((elapsed, travelled))
            earlier = [d for t, d in log if t <= elapsed - self.DIST_STALL_WINDOW_S]
            if earlier and travelled - earlier[-1] < self.DIST_STALL_MIN_M:
                status = " status=blocked"
                break
        print(f"[MOVE] target={target:.2f} m final_error={travelled - target:.2f} m{status}")
        return travelled


def _target(cmd) -> str:
    return f"{cmd.color} {cmd.object_class}".strip()


def _mission_summary(mission, n_goals: int, elapsed: float) -> str:
    """SUCCESS = every goal reached; PARTIAL = some; FAIL = none. Goals never
    attempted (the batch ended on an error) count as not reached."""
    reached = [c for c, ok in mission if ok]
    missed = [c for c, ok in mission if not ok]
    status = ("SUCCESS" if len(reached) == n_goals else
              "PARTIAL" if reached else "FAIL")
    out = f"[MULTI] status={status} reached={len(reached)}/{n_goals}"
    if missed:
        out += " missed=" + ",".join(_target(c).replace(" ", "_") for c in missed)
    if len(mission) < n_goals:
        out += f" not_attempted={n_goals - len(mission)}"
    return out + f" t={elapsed:.1f} s"


def _short_error(e: Exception, limit: int = 80) -> str:
    msg = " ".join(str(e).split())
    if len(msg) > limit:
        msg = msg[:limit - 3] + "..."
    return f"{type(e).__name__}: {msg}"
