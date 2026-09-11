"""
llm_parser.py — STUDENT B OWNS THIS FILE. Part of Task 3 (60%).

Converts one free-form English utterance (+ dialogue history) into a
schema.ParseResult using an LLM with structured (JSON) output. Depends on
nothing but `schema` and whichever LLM SDK you call — no dependency on
Student A's or Student C's code, so you can build and test this in
complete isolation (see tests/test_parser_with_mock.py).

Swap LLM_SERVICE in config.py to compare >=2 services for Task 3.iv.
"""

import json
from typing import List, Dict

from core.schema import (
    ParseResult, MoveCommand, TurnCommand, GotoObjectCommand,
    StopCommand, ChatCommand,
)
from core import config

SYSTEM_PROMPT = """You are a command parser for a quadruped robot.
Convert the user's English instruction into a JSON list of actions using
ONLY this schema:
  {"action": "move", "vx": float[-1,1], "vy": float[-1,1], "wz": float[-1,1], "duration": float_seconds}
  {"action": "turn", "angle_deg": float}   // positive = left
  {"action": "goto_object", "class": string, "color": string}
  {"action": "stop"}
  {"action": "chat", "reply": string}
Rules:
- Multi-step instructions become an ordered list of actions.
- Reject (return {"rejected": true, "reason": "..."}) anything unsafe,
  impossible, empty, or NOT in English.
- Respond with ONLY the JSON. No prose, no markdown fences.
"""


def parse_command(user_text: str, history: List[Dict[str, str]]) -> ParseResult:
    """history is a list of {"role": "user"/"assistant", "content": str}
    dialogue turns, maintained by chat_interface.py, so follow-ups like
    'do that again, but slower' can be resolved."""
    raw = _call_llm(user_text, history)
    return _to_parse_result(raw)


def _call_llm(user_text: str, history: List[Dict[str, str]]) -> str:
    """TODO(Student B): call config.LLM_SERVICE (OpenAI / Qwen / Gemini /
    Ollama — pick >=2 for the Task 3.iv comparison). Return the raw JSON
    string from the model. Keep this a pure text-only call (no images)."""
    raise NotImplementedError


def _to_parse_result(raw_json: str) -> ParseResult:
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        reason = "malformed_json"
        print(f"[CMD] rejected reason={reason}")
        return ParseResult(accepted=False, reject_reason=reason)

    if isinstance(data, dict) and data.get("rejected"):
        reason = data.get("reason", "unspecified")
        print(f"[CMD] rejected reason={reason}")
        return ParseResult(accepted=False, reject_reason=reason)

    actions = data if isinstance(data, list) else data.get("actions", [])
    commands = []
    for a in actions:
        kind = a.get("action")
        if kind == "move":
            commands.append(MoveCommand(a["vx"], a["vy"], a["wz"], a["duration"]))
        elif kind == "turn":
            commands.append(TurnCommand(a["angle_deg"]))
        elif kind == "goto_object":
            commands.append(GotoObjectCommand(a["class"], a["color"]))
        elif kind == "stop":
            commands.append(StopCommand())
        elif kind == "chat":
            commands.append(ChatCommand(a["reply"]))
        else:
            print(f"[CMD] rejected reason=unknown_action:{kind}")
            return ParseResult(accepted=False, reject_reason=f"unknown_action:{kind}")

    summary = ", ".join(_describe(c) for c in commands)
    print(f"[CMD] actions={summary} n={len(commands)}")
    return ParseResult(accepted=True, commands=commands)


def _describe(c) -> str:
    if isinstance(c, MoveCommand):
        return f"move(vx={c.vx}, {c.duration} s)"
    if isinstance(c, TurnCommand):
        return f"turn({c.angle_deg} deg)"
    if isinstance(c, GotoObjectCommand):
        return f"goto_object(class={c.object_class}, color={c.color})"
    if isinstance(c, StopCommand):
        return "stop"
    if isinstance(c, ChatCommand):
        return "chat"
    return str(c)
