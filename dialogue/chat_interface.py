"""
chat_interface.py — STUDENT B OWNS THIS FILE. Part of Task 3 (60%).

Runs the terminal chat loop in its own thread so the simulation (main
thread, via executor.run_forever) never blocks on input() or the LLM call.
Maintains dialogue history and rejects/flags non-English input.
"""

import threading
from typing import List, Dict

from core import config
from core.schema import CommandQueue
from dialogue import llm_parser


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


def handle_utterance(user_text: str, history: List[Dict[str, str]],
                     queue: CommandQueue):
    """Parse one utterance against the PREVIOUS turns, queue the accepted
    commands, then record the exchange in `history` (trimmed to the last
    config.LLM_HISTORY_TURNS exchanges). Returns the ParseResult."""
    result = llm_parser.parse_command(user_text, history)
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
