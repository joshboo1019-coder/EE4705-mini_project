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


class CommandExecutor:
    def __init__(self, skills: SkillsAPI, perception: PerceptionAPI,
                 queue: CommandQueue,
                 goto_object_fn: Callable = navigation.goto_object):
        self.skills = skills
        self.perception = perception
        self.queue = queue
        self.goto_object_fn = goto_object_fn

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
        for i, cmd in enumerate(batch, start=1):
            self._exec_one(cmd, i, n)
        elapsed = time.time() - t0
        print(f"[DONE] actions={n} t={elapsed:.1f} s")

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
        else:
            print(f"[EXEC] action={i}/{n} unknown command skipped: {cmd}")
