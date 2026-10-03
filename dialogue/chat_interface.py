"""
chat_interface.py — STUDENT B OWNS THIS FILE. Part of Task 3 (60%).

Runs the terminal chat loop in its own thread so the simulation (main
thread, via executor.run_forever) never blocks on input() or the LLM call.
Maintains dialogue history and rejects/flags non-English input.

Safety reflex — the stop fast path. An utterance that is exactly a stop
word (STOP_WORDS; case, punctuation and extra spaces ignored: "stop",
"Stop!", "halt", "freeze", "stop now", "emergency stop", "abort", ...)
never waits for the LLM: right here on the chat thread it sets the
executor's abort flag, calls skills.stop() and clears the queue
(executor.emergency_stop), then prints `[ESTOP] latency=<ms> ms`. This
works while the executor thread is busy mid-program; the program ends at
its next step boundary (see executor.py for exactly what is interrupted).
Every other utterance — including stop-ish phrases that are not exact
stop words, e.g. "careful, stop there" — still goes through the LLM, which
maps them to the ordinary stop action as before. The fast path is only
active when an executor is bound to the queue (dialogue/runtime.py), i.e.
in main.py's real loop.
"""

import re
import threading
import time
from typing import List, Dict

from core import config
from core.schema import CommandQueue, ParseResult, StopCommand
from dialogue import llm_parser, runtime, talkback

STOP_WORDS = frozenset({
    "stop", "halt", "freeze", "abort", "stop now", "halt now", "freeze now",
    "stop it", "stop stop", "stop stop stop", "stop right now", "stop right there",
    "please stop", "stop please", "emergency stop", "e stop", "estop", "abort abort",
})


def start_chat_thread(queue: CommandQueue) -> threading.Thread:
    t = threading.Thread(target=_chat_loop, args=(queue,), daemon=True)
    t.start()
    return t


def _chat_loop(queue: CommandQueue) -> None:
    history: List[Dict[str, str]] = []
    print("Type an English command and press ENTER (Ctrl+C to quit).")
    print("To speak instead, type v + ENTER and talk (up to 5 s).")
    while True:
        try:
            user_text = input("User: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_text:
            continue
        if user_text.lower() == "v":
            # Push-to-talk. Imported here so typed-only use never loads whisper.
            from dialogue import speech_input
            try:
                speech_input.handle_voice(history, queue)
            except Exception as e:
                print(f"[STT] failed reason={type(e).__name__}: {e}")
            continue
        handle_utterance(user_text, history, queue)


def is_stop_word(text: str) -> bool:
    norm = " ".join(re.sub(r"[^a-z]+", " ", (text or "").lower()).split())
    return norm in STOP_WORDS


def handle_utterance(user_text: str, history: List[Dict[str, str]],
                     queue: CommandQueue):
    """Parse one utterance against the PREVIOUS turns, queue the accepted
    commands, then record the exchange in `history` (trimmed to the last
    config.LLM_HISTORY_TURNS exchanges). Returns the ParseResult."""
    t0 = time.perf_counter()
    executor = runtime.executor_for(queue)
    if executor is not None and is_stop_word(user_text):
        return _emergency_stop(executor, user_text, history, t0)
    # the robot's compact state (pose vs start, last actions, YOLO sightings)
    # goes in front of the utterance, so "the first thing you saw" can resolve
    snapshot = executor.state.snapshot() if executor is not None else None
    result = llm_parser.parse_command(user_text, history, snapshot=snapshot)
    if not result.accepted:
        if (result.reject_reason == "non-English" and getattr(result, "precheck", False)
                and not getattr(result, "suggestion", None)):
            # the precheck made no LLM call, so this is still <= 1 per utterance
            result.suggestion = llm_parser.suggest_english(user_text)
        say_rejection(result, user_text, queue)
    remember(user_text, result, history)

    if result.accepted:
        queue.push_many(result.commands)
        # NOTE: do not wait for [DONE] here — the executor thread handles
        # execution independently, which is what keeps this loop responsive
        # for the next typed command.
    return result


def remember(user_text: str, result, history: List[Dict[str, str]]) -> None:
    """Record one exchange in `history`, trimmed to the last
    config.LLM_HISTORY_TURNS exchanges. The assistant turn is the accepted
    actions as JSON (or the reject reason), so "do that again, but slower"
    can see what "that" was."""
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant",
                    "content": llm_parser.history_entry(result)})
    del history[:-2 * config.LLM_HISTORY_TURNS]


def say_rejection(result, user_text: str = "", queue=None) -> None:
    """`Robot: ...` right after `[CMD] rejected reason=...` (talkback.py):
    an English suggestion for non-English input, a valid alternative for an
    out-of-range request. Templates only; the suggestion is never executed.
    The rejection is also kept in the robot state ("why did you reject that?")."""
    suggestion = getattr(result, "suggestion", None)
    reply = talkback.reject_reply(result.reject_reason, suggestion)
    if reply:
        print(f"Robot: {reply}")
    executor = runtime.executor_for(queue) if queue is not None else None
    if executor is not None and result.reject_reason != "empty":
        executor.state.record_reject(user_text, result.reject_reason, suggestion)


def _emergency_stop(executor, user_text: str, history: List[Dict[str, str]],
                    t0: float) -> ParseResult:
    """The stop fast path (module docstring). No LLM call, nothing queued."""
    was_running = executor.emergency_stop()
    print(f"[ESTOP] latency={(time.perf_counter() - t0) * 1000:.1f} ms")
    if not was_running:
        print("Robot: Stopped.")
    result = ParseResult(accepted=True, commands=[StopCommand()])
    remember(user_text, result, history)
    return result
