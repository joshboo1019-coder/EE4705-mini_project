"""
executor.py — STUDENT B OWNS THIS FILE. Part of Task 3 (60%).

Pops commands off schema.CommandQueue and runs them in order via the
SkillsAPI (Student A) and navigation.goto_object (Student C). This is the
one place where all three tasks meet — but note it only ever calls the
*interfaces*, so it can be fully tested with skills_mock + perception_mock
before Task 2/4 are finished (tests/test_student_b.py and tests/test_upgrade_b.py do this).

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
    StatusCommand, UndoCommand, ReturnHomeCommand,
)
from dialogue.limits import kind, wrap_deg
from dialogue.state import ActionRecord, RecordingPerception, RobotState, NOT_LOGGED


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

    # RealSkills.turn() aims at wrap(start + angle), so a turn of more than
    # 180 deg goes the short way (turn(360) does nothing, turn(270) turns
    # right 90). Larger turns are split into equal chunks of at most this.
    MAX_TURN_CHUNK_DEG = 120.0

    def turn(self, angle_deg: float) -> None:
        n = max(1, math.ceil(abs(angle_deg) / self.MAX_TURN_CHUNK_DEG - 1e-9)) \
            if abs(angle_deg) > 180.0 else 1
        for _ in range(n):
            if self._aborted():
                raise ExecutionAborted()
            self._inner.turn(angle_deg / n)

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
        # every detection anyone makes through this executor (navigation,
        # look, until_see) is recorded in the state store — YOLO only
        self.state = RobotState()
        self.perception = RecordingPerception(perception, self.state, self._pose)
        self.queue = queue
        self.goto_object_fn = goto_object_fn
        self.vlm_fn = vlm_fn
        self.save_frame_fn = save_frame_fn
        self._estop_lock = threading.Lock()
        self._estop_count = 0
        self._batch_estop = 0       # _estop_count when the running batch started
        self._busy = False
        self._motion = _AbortableSkills(skills, self._aborted)
        self._pose()              # the first pose seen is "home"
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
        batch_id = self.state.new_batch()
        trace = talkback.BatchTrace(kinds=[kind(c) for c in batch], pose_before=self._pose())
        self._path_m, self._path_pose = 0.0, trace.pose_before
        # Two or more goto_object actions in one utterance form a multi-goal
        # mission: each goal is reported, a goal that isn't reached is
        # skipped (the robot goes on to the next one), and a [MULTI] summary
        # closes the batch.
        n_goals = sum(isinstance(c, GotoObjectCommand) for c in batch)
        mission = [] if n_goals >= 2 else None
        for i, cmd in enumerate(batch, start=1):
            # This runs on the main thread: a skill or navigation error must
            # not kill the program, so it ends this batch and nothing more.
            pose_before = self._pose()
            try:
                self._check_abort()
                reached = self._exec_one(cmd, i, n, trace)
            except ExecutionAborted:
                print(f"[EXEC] action={i}/{n} aborted reason=emergency_stop")
                trace.aborted_at = i
                self._log(batch_id, cmd, pose_before, completed=False)
                break
            except Exception as e:
                print(f"[EXEC] action={i}/{n} failed reason={_short_error(e)}")
                self._safe_stop()
                trace.failed = (i, _short_error(e, limit=40))
                self._log(batch_id, cmd, pose_before, completed=False)
                break
            self._log(batch_id, cmd, pose_before, completed=True, result=reached)
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
        self._track()
        trace.path_m = self._path_m
        line = talkback.summary(trace)
        if line:
            print(f"Robot: {line}")

    def _pose(self):
        """Current pose (also kept in the state store); None if the skills
        can't say."""
        try:
            pose = self.skills.get_robot_pose()
        except Exception:
            return None
        self.state.update_pose(pose)
        return pose

    def _track(self) -> None:
        """Add the straight-line distance since the last sample to the
        batch's path length (sampled after every step and distance slice)."""
        p = self._pose()
        if p is not None and getattr(self, "_path_pose", None) is not None:
            self._path_m += math.hypot(p.x - self._path_pose.x, p.y - self._path_pose.y)
        self._path_pose = p if p is not None else getattr(self, "_path_pose", None)

    def _log(self, batch_id, cmd, pose_before, completed, result=None) -> None:
        if kind(cmd) in NOT_LOGGED:
            return
        if isinstance(cmd, UndoCommand) and getattr(cmd, "_undid", None) is None:
            return            # nothing was undone, nothing moved
        self.state.record_action(ActionRecord(
            batch=batch_id, command=cmd, pose_before=pose_before, pose_after=self._pose(),
            completed=completed, result=result, is_undo=isinstance(cmd, UndoCommand)))

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

    def _exec_one(self, cmd, i: int, n: int, trace=None):
        """Runs one command; returns goto_object's result (True = reached),
        or (seen, iterations) for until_see. Steps inside a program are run
        through here too and log with their top-level action number."""
        try:
            return self._exec_step(cmd, i, n, trace)
        finally:
            if hasattr(self, "_path_m"):
                self._track()

    def _exec_step(self, cmd, i: int, n: int, trace=None):
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
        elif isinstance(cmd, StatusCommand):
            print(f"[EXEC] action={i}/{n} status topic={cmd.topic}")
            print(f"Robot: {self.state.answer(cmd.topic)}")
        elif isinstance(cmd, UndoCommand):
            self._undo(cmd, i, n, trace)
        elif isinstance(cmd, ReturnHomeCommand):
            home = self.state.home
            print(f"[EXEC] action={i}/{n} return_home")
            if home is None:
                raise RuntimeError("no home pose recorded")
            self._go_to_pose(home, "return home")
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

    # ------------------------------------------------------------------
    # repair: undo / return_home (motion computed by code from the log)
    # ------------------------------------------------------------------

    def _undo(self, cmd: UndoCommand, i: int, n: int, trace) -> None:
        """Invert the last undoable record: a turn turns back by the
        opposite angle; a straight move (timed or distance, no wz) walks
        back the distance it actually covered at the reversed velocity,
        then restores the heading; anything else (goto_object, a program,
        a curved move, return_home) goes back to the pose before it."""
        rec = self.state.last_undoable()
        if rec is None:
            print(f"[EXEC] action={i}/{n} undo nothing_to_undo")
            if trace is not None:
                trace.notes.append("there was nothing to undo")
            print("Robot: There's nothing to undo.")
            return
        c = rec.command
        print(f"[EXEC] action={i}/{n} undo of={rec.words()}")
        cmd._undid = rec
        if rec.kind == "turn":
            print(f"[PLAN] undo: {talkback.words(TurnCommand(-c.angle_deg))}")
            self._motion.turn(-c.angle_deg)
        elif rec.kind in ("move", "move_distance") and abs(c.wz) < 0.05:
            p0, p1 = rec.pose_before, rec.pose_after
            dist = math.hypot(p1.x - p0.x, p1.y - p0.y) if p0 and p1 else 0.0
            s = -1.0 if getattr(c, "distance_m", 1.0) < 0 else 1.0
            back = DistanceMoveCommand(-c.vx * s, -c.vy * s, 0.0, round(dist, 2))
            steps = [back] if dist >= 0.05 else []
            fix = wrap_deg(p0.yaw_deg - self.skills.get_robot_pose().yaw_deg) if p0 else 0.0
            if abs(fix) > 3.0:
                steps.append(TurnCommand(round(fix, 1)))
            print(f"[PLAN] undo: {talkback.join(steps) if steps else 'nothing moved'}")
            if dist >= 0.05:
                self._walk_distance(back.vx, back.vy, 0.0, back.distance_m)
            if abs(fix) > 3.0:
                self._motion.turn(round(fix, 1))
        else:
            if rec.pose_before is None:
                raise RuntimeError("no pose recorded before that action")
            self._go_to_pose(rec.pose_before, "undo")
        rec.undone = True

    def _go_to_pose(self, target, label: str, speed: float = limits.NORMAL_SPEED) -> None:
        """Turn to face `target`, walk the straight-line distance closed-loop,
        turn to its heading. Prints the computed [PLAN] first."""
        p = self.skills.get_robot_pose()
        dist = math.hypot(target.x - p.x, target.y - p.y)
        steps = []
        heading = p.yaw_deg
        if dist > 0.15:
            bearing = math.degrees(math.atan2(target.y - p.y, target.x - p.x))
            face = round(wrap_deg(bearing - p.yaw_deg), 1)
            if abs(face) > 2.0:
                steps.append(TurnCommand(face))
            steps.append(DistanceMoveCommand(speed, 0.0, 0.0, round(dist, 2)))
            heading = bearing
        final = round(wrap_deg(target.yaw_deg - heading), 1)
        if abs(final) > 2.0:
            steps.append(TurnCommand(final))
        print(f"[PLAN] {label}: {talkback.join(steps) if steps else 'already there'}")
        for st in steps:
            self._check_abort()
            if isinstance(st, DistanceMoveCommand):
                self._walk_distance(st.vx, st.vy, st.wz, st.distance_m)
            elif st is steps[0] and len(steps) > 1:
                self._motion.turn(st.angle_deg)          # face the target
        # the final heading is computed from where the robot actually ended
        # up (the plan's last turn assumed a perfect walk)
        p = self.skills.get_robot_pose()
        err = round(wrap_deg(target.yaw_deg - p.yaw_deg), 1)
        if abs(err) > 2.0:
            self._check_abort()
            self._motion.turn(err)

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
            if hasattr(self, "_path_m"):
                self._track()
            earlier = [d for t, d in log if t <= elapsed - self.DIST_STALL_WINDOW_S]
            if earlier and travelled - earlier[-1] < self.DIST_STALL_MIN_M:
                status = " status=blocked"
                break
        err = round(travelled - target, 2) + 0.0          # no "-0.00"
        print(f"[MOVE] target={target:.2f} m final_error={err:.2f} m{status}")
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
