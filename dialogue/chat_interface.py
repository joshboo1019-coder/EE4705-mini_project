"""
chat_interface.py — STUDENT B OWNS THIS FILE. Part of Task 3 (60%).

Runs the terminal chat loop in its own thread so the simulation (main
thread, via executor.run_forever) never blocks on input() or the LLM call.
Maintains dialogue history and rejects/flags non-English input.
"""

import threading
from typing import List, Dict

from core.schema import CommandQueue
from dialogue import llm_parser


def start_chat_thread(queue: CommandQueue) -> threading.Thread:
    t = threading.Thread(target=_chat_loop, args=(queue,), daemon=True)
    t.start()
    return t


def _chat_loop(queue: CommandQueue) -> None:
    history: List[Dict[str, str]] = []
    print("Type an English command and press ENTER (Ctrl+C to quit).")
    while True:
        try:
            user_text = input("User: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_text:
            continue

        history.append({"role": "user", "content": user_text})
        result = llm_parser.parse_command(user_text, history)

        if not result.accepted:
            history.append({"role": "assistant",
                             "content": f"rejected: {result.reject_reason}"})
            continue

        history.append({"role": "assistant",
                         "content": f"accepted {len(result.commands)} action(s)"})
        queue.push_many(result.commands)
        # NOTE: do not wait for [DONE] here — the executor thread handles
        # execution independently, which is what keeps this loop responsive
        # for the next typed command.
