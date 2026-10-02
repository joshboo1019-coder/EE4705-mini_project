"""
executor.py — STUDENT B OWNS THIS FILE. Part of Task 3 (60%).

Pops commands off schema.CommandQueue and runs them in order via the
SkillsAPI (Student A) and navigation.goto_object (Student C). This is the
one place where all three tasks meet — but note it only ever calls the
*interfaces*, so it can be fully tested with skills_mock + perception_mock
before Task 2/4 are finished (tests/test_parser_with_mock.py does this).
"""

import time
from typing import Callable

from core.interfaces import SkillsAPI, PerceptionAPI
from core.schema import (
    CommandQueue, MoveCommand, TurnCommand, GotoObjectCommand,
    StopCommand, ChatCommand,
)
from perception import navigation
from dialogue import vlm
from dialogue.commands import LookCommand


class CommandExecutor:
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

    def run_forever(self, poll_timeout: float = 0.2) -> None:
        """Call this from the main thread's loop (not the chat thread) so
        the simulation keeps stepping while it also executes commands."""
        while True:
            cmd = self.queue.pop(timeout=poll_timeout)
            if cmd is not None:
                self._run_batch_starting_with(cmd)

    def _run_batch_starting_with(self, first_cmd) -> None:
        """Runs `first_cmd` and then drains any remaining queued commands
        from the SAME parsed utterance as one [EXEC]...[DONE] sequence."""
        batch = [first_cmd]
        while not self.queue.empty():
            nxt = self.queue.pop(timeout=0.0)
            if nxt is None:
                break
            batch.append(nxt)

        t0 = time.time()
        n = len(batch)
        done = 0
        for i, cmd in enumerate(batch, start=1):
            # This runs on the main thread: a skill or navigation error must
            # not kill the program, so it ends this batch and nothing more.
            try:
                self._exec_one(cmd, i, n)
            except Exception as e:
                print(f"[EXEC] action={i}/{n} failed reason={_short_error(e)}")
                self._safe_stop()
                break
            done += 1
        elapsed = time.time() - t0
        print(f"[DONE] actions={done} t={elapsed:.1f} s")

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

    def _exec_one(self, cmd, i: int, n: int) -> None:
        if isinstance(cmd, MoveCommand):
            print(f"[EXEC] action={i}/{n} move vx={cmd.vx} vy={cmd.vy} "
                  f"wz={cmd.wz} t={cmd.duration} s")
            self.skills.move(cmd.vx, cmd.vy, cmd.wz, cmd.duration)
        elif isinstance(cmd, TurnCommand):
            print(f"[EXEC] action={i}/{n} turn angle={cmd.angle_deg} deg")
            self.skills.turn(cmd.angle_deg)
        elif isinstance(cmd, GotoObjectCommand):
            print(f"[EXEC] action={i}/{n} goto_object class={cmd.object_class} "
                  f"color={cmd.color}")
            self.goto_object_fn(cmd.object_class, cmd.color,
                                 self.skills, self.perception)
        elif isinstance(cmd, StopCommand):
            print(f"[EXEC] action={i}/{n} stop")
            self.skills.stop()
            self.queue.clear()
        elif isinstance(cmd, ChatCommand):
            print(f"Robot: {cmd.reply}")
        elif isinstance(cmd, LookCommand):
            print(f'[EXEC] action={i}/{n} look question="{cmd.question}"')
            self._look(cmd.question)
        else:
            print(f"[EXEC] action={i}/{n} unknown command skipped: {cmd}")


def _short_error(e: Exception, limit: int = 80) -> str:
    msg = " ".join(str(e).split())
    if len(msg) > limit:
        msg = msg[:limit - 3] + "..."
    return f"{type(e).__name__}: {msg}"
