"""
llm_parser.py — STUDENT B OWNS THIS FILE. Part of Task 3 (60%).

Converts one free-form English utterance (+ dialogue history) into a
schema.ParseResult using an LLM with structured (JSON) output. Depends on
nothing but `schema` and whichever LLM SDK you call — no dependency on
Student A's or Student C's code, so you can build and test this in
complete isolation (see tests/test_student_b.py).

Swap LLM_SERVICE in config.py to compare >=2 services for Task 3.iv.
All three services (Qwen, Gemini, OpenAI) are reached through the `openai`
SDK's chat-completions API; Qwen and Gemini via their OpenAI-compatible
endpoints. The LLM output is never trusted as-is: _to_parse_result()
re-validates every field before anything reaches the CommandQueue
(docs/DECISIONS.md §5).
"""

import json
import math
import os
import re
import time
from pathlib import Path
from typing import List, Dict, Optional

from core.schema import (
    ParseResult, MoveCommand, TurnCommand, GotoObjectCommand,
    StopCommand, ChatCommand,
)
from core import config
from dialogue.commands import LookCommand

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# LLM services. Keys are the values config.LLM_SERVICE may take.
# ---------------------------------------------------------------------------

PROVIDERS = {
    # Alibaba Cloud Model Studio, international (Singapore) region ONLY —
    # the key is not valid for the mainland-China endpoint.
    "qwen": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "key_env": "DASHSCOPE_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GOOGLE_API_KEY",
    },
    "openai": {
        "base_url": None,  # SDK default (api.openai.com)
        "key_env": "OPENAI_API_KEY",
    },
}

# service name -> (provider, model id, extra request params). The extra
# params are optional tuning: if a model rejects one (HTTP 400 naming that
# parameter) it is dropped and the call retried, never forced.
SERVICES = {
    "qwen-flash": ("qwen", "qwen-flash", {"temperature": 0}),
    "qwen-plus": ("qwen", "qwen-plus", {"temperature": 0}),
    # gemini-2.5-flash returns 404 "no longer available to new users", so
    # the current Flash model is used. It "thinks" by default;
    # reasoning_effort=none turns that off on the OpenAI-compatible
    # endpoint (~1.5 s instead of ~4-6 s). Temperature left at the default
    # (Google advises against lowering it for Gemini 3).
    "gemini-3.8-flash": ("gemini", "gemini-3.8-flash",
                         {"reasoning_effort": "none"}),
    # gpt-5 family: reasoning models, no temperature; minimal reasoning
    # keeps latency acceptable for a chat loop.
    "gpt-5-nano": ("openai", "gpt-5-nano", {"reasoning_effort": "minimal"}),
    "gpt-5-mini": ("openai", "gpt-5-mini", {"reasoning_effort": "minimal"}),
}

# Filled in by every _call_llm() call (successful or not) for the Task 3.iv
# evaluation: service, model, latency_s, prompt_tokens, completion_tokens,
# attempts, error.
last_call_stats: Dict[str, object] = {}

# Lazily-built clients, one per provider.
_clients: Dict[str, object] = {}

# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


def load_api_key(name: str, env_file: Optional[Path] = None) -> Optional[str]:
    """Return API key `name`: os.environ first, then the repo-root .env
    (via python-dotenv). Never overrides an already-set environment
    variable and never prints the value."""
    value = os.environ.get(name)
    if value:
        return value
    env_file = Path(env_file) if env_file is not None else REPO_ROOT / ".env"
    if not env_file.is_file():
        return None
    from dotenv import dotenv_values
    return dotenv_values(env_file).get(name) or None


def _get_client(provider: str):
    if provider not in _clients:
        from openai import OpenAI
        spec = PROVIDERS[provider]
        key = load_api_key(spec["key_env"])
        if not key:
            raise RuntimeError(f"missing API key {spec['key_env']}")
        _clients[provider] = OpenAI(api_key=key, base_url=spec["base_url"],
                                    timeout=config.LLM_TIMEOUT_S,
                                    max_retries=0)  # retries handled below
    return _clients[provider]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the command parser for a quadruped robot dog. Convert
the user's English instruction into JSON. Respond with ONE JSON object only,
no prose, no markdown fences, in exactly one of these two shapes:
  {"actions": [ <action>, ... ]}
  {"rejected": true, "reason": "<short_reason>"}

Each <action> is one of:
  {"action": "move", "vx": float, "vy": float, "wz": float, "duration": float}
      vx forward(+)/backward(-), vy left(+)/right(-), wz turn-left(+) rate;
      each in [-1, 1]; duration in seconds, > 0 and <= 30. Always give all
      four fields (use 0.0 for unused axes).
  {"action": "turn", "angle_deg": float}
      in-place turn; positive = left (counter-clockwise), negative = right.
  {"action": "goto_object", "class": string, "color": string}
      find and walk to an object. "class" MUST be a COCO class name
      (e.g. "chair", "sports ball", "stop sign", "bottle", "person"); map
      synonyms ("ball" -> "sports ball", "seat" -> "chair"). "color" is a
      lowercase color word, "" if the user gave none.
  {"action": "stop"}
  {"action": "chat", "reply": string}
      a short spoken reply: answer a question about the robot, or ask a
      clarifying question when the request is ambiguous. Produces no motion.
  {"action": "look", "question": string}
      answer a question about what the robot can SEE right now (its camera
      view is sent to a vision model). "question" is the user's question,
      cleaned up. Produces no motion. Use it only for an actual question
      or request about what is visible. An exclamation or warning that
      happens to contain "look" (like "careful!") is not a look action;
      treat a warning as stop.

Sign convention (robot's own point of view; get this right):
- vx  + = forward,  - = backward
- vy  + = LEFT,     - = RIGHT       ("left" is POSITIVE vy)
- wz  + = turn left (counter-clockwise),  - = turn right
- turn angle_deg  + = left,  - = right

Conventions:
- Normal walking speed vx=0.8; "slowly" ~0.3-0.4; "fast"/"run" 1.0;
  "a bit"/"a little"/"a few steps" = 1.5 s. No duration given = 2 s.
- If a distance is given, assume speed in m/s ~= vx (e.g. 2 m at vx=0.8 -> 2.5 s).
- "turn back"/"turn around" = 180; "turn left" = 90; "turn right" = -90.
- "stop", "halt", "freeze", "stop now" and similar all map to
  {"actions": [{"action": "stop"}]}; never reject them as empty.
- Multi-step instructions become an ordered list, in the order spoken.
- Follow-ups ("do that again", "now slower", "the other way") refer to the
  previous accepted actions in the conversation; reuse and modify them.
- Decide the language first: an instruction that is not in English is
  rejected as "non-English" even if you understand it.
- Reject with a short snake_case reason when the request is:
  not in English -> "non-English"; empty or meaningless -> "empty";
  physically impossible for a walking robot dog (fly, swim, climb walls,
  jump onto the roof, pick things up) -> "impossible:<what>";
  dangerous to people, the robot, or property -> "unsafe:<what>";
  beyond the limits above (e.g. > 30 s, faster than max) -> "out_of_range:<what>".
- If it is unclear WHAT the user wants, use a single chat action asking
  for clarification instead of guessing.

Examples:
User: walk forward for three seconds, then turn back
{"actions": [{"action": "move", "vx": 0.8, "vy": 0.0, "wz": 0.0, "duration": 3.0}, {"action": "turn", "angle_deg": 180}]}
User: turn right 90 degrees
{"actions": [{"action": "turn", "angle_deg": -90}]}
User: move left for two seconds
{"actions": [{"action": "move", "vx": 0.0, "vy": 0.8, "wz": 0.0, "duration": 2.0}]}
User: strafe right a bit
{"actions": [{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 1.5}]}
User: could you walk forwards a bit
{"actions": [{"action": "move", "vx": 0.8, "vy": 0.0, "wz": 0.0, "duration": 1.5}]}
User: go to the green chair
{"actions": [{"action": "goto_object", "class": "chair", "color": "green"}]}
User: back up slowly for 2 seconds and then stop
{"actions": [{"action": "move", "vx": -0.3, "vy": 0.0, "wz": 0.0, "duration": 2.0}, {"action": "stop"}]}
User: fly to the roof
{"rejected": true, "reason": "impossible:fly"}
User: what's in front of you?
{"actions": [{"action": "look", "question": "what's in front of you?"}]}
User: turn right and tell me if you see anything red
{"actions": [{"action": "turn", "angle_deg": -90}, {"action": "look", "question": "do you see anything red?"}]}
User: what can you do?
{"actions": [{"action": "chat", "reply": "I can walk, turn, stop, and walk to objects like the green chair."}]}
"""

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

MAX_DURATION_S = getattr(config, "LLM_MAX_DURATION_S", 30.0)
MAX_LOOK_QUESTION_CHARS = 300
NON_ASCII_LETTER_RATIO = 0.3

# The 80 COCO class names YOLO (Task 4) can detect.
COCO_CLASSES = {
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
}


class _Invalid(Exception):
    """Validation failure; args[0] is the reject reason."""


def parse_command(user_text: str, history: List[Dict[str, str]]) -> ParseResult:
    """history is a list of {"role": "user"/"assistant", "content": str}
    PREVIOUS dialogue turns (not including user_text), maintained by
    chat_interface.py, so follow-ups like 'do that again, but slower' can
    be resolved. Never raises: LLM/network failures come back as a
    rejected ParseResult with reason=llm_error:<ExceptionType>."""
    pre = precheck(user_text)
    if pre is not None:
        return _reject(pre)
    try:
        raw = _call_llm(user_text, history)
    except NotImplementedError:
        raise
    except Exception as e:  # network, timeout, auth, rate limit, ...
        return _reject(f"llm_error:{type(e).__name__}")
    return _to_parse_result(raw)


def precheck(user_text: str) -> Optional[str]:
    """Cheap pre-LLM filter. Returns a reject reason, or None to continue.
    Only catches the obvious cases (empty, mostly non-Latin script); the
    LLM itself still rejects e.g. French or German written in ASCII."""
    text = (user_text or "").strip()
    if not text:
        return "empty"
    letters = [c for c in text if c.isalpha()]
    if letters:
        non_ascii = sum(1 for c in letters if ord(c) > 127)
        if non_ascii / len(letters) > NON_ASCII_LETTER_RATIO:
            return "non-English"
    return None


def _call_llm(user_text: str, history: List[Dict[str, str]]) -> str:
    """Call config.LLM_SERVICE and return the model's raw text. Text-only,
    JSON mode on, timeout config.LLM_TIMEOUT_S, at most one retry on a
    network error or a 5xx (e.g. Gemini's 503 "high demand"). Latency / token usage land in `last_call_stats`."""
    from openai import (APIConnectionError, APITimeoutError,
                        BadRequestError, InternalServerError)

    service = config.LLM_SERVICE
    if service not in SERVICES:
        raise ValueError(f"unknown LLM_SERVICE {service!r}; "
                         f"choose one of {sorted(SERVICES)}")
    provider, model, extra = SERVICES[service]
    client = _get_client(provider)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_text})
    params = dict(extra)
    params["response_format"] = {"type": "json_object"}

    last_call_stats.clear()
    last_call_stats.update(service=service, model=model, latency_s=None,
                           prompt_tokens=None, completion_tokens=None,
                           attempts=0, error=None)
    network_retries_left = 1
    t0 = time.perf_counter()
    while True:
        last_call_stats["attempts"] += 1
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, **params)
            break
        except (APIConnectionError, APITimeoutError,
                InternalServerError) as e:
            if network_retries_left > 0:
                network_retries_left -= 1
                if isinstance(e, InternalServerError):
                    time.sleep(1.0)
                continue
            _finish_stats(t0, error=e)
            raise
        except BadRequestError as e:
            dropped = _droppable_param(e, params)
            if dropped is None:
                _finish_stats(t0, error=e)
                raise
            params.pop(dropped)
        except Exception as e:
            _finish_stats(t0, error=e)
            raise

    usage = getattr(resp, "usage", None)
    _finish_stats(t0,
                  prompt_tokens=getattr(usage, "prompt_tokens", None),
                  completion_tokens=getattr(usage, "completion_tokens", None))
    return resp.choices[0].message.content or ""


def _finish_stats(t0: float, error: Optional[Exception] = None, **kw) -> None:
    last_call_stats["latency_s"] = time.perf_counter() - t0
    if error is not None:
        last_call_stats["error"] = type(error).__name__
    last_call_stats.update(kw)


def _droppable_param(err: Exception, params: Dict) -> Optional[str]:
    """If a 400 error names one of our optional params, return its name so
    the call can be retried without it."""
    msg = str(err).lower()
    for name in params:
        if any(word in msg for word in _PARAM_ERROR_WORDS.get(name, (name,))):
            return name
    return None


# How each provider's 400 message refers to an optional parameter, e.g.
# Gemini says "Thinking level MINIMAL is not supported" for reasoning_effort.
_PARAM_ERROR_WORDS = {
    "reasoning_effort": ("reasoning_effort", "reasoning effort", "thinking"),
    "temperature": ("temperature",),
    "response_format": ("response_format", "json mode", "json_object"),
}


def history_entry(result: ParseResult) -> str:
    """The assistant turn chat_interface.py stores in the history: the same
    JSON shape the model is asked to produce, so a follow-up can see (and
    modify) exactly which actions were accepted."""
    if not result.accepted:
        return json.dumps({"rejected": True, "reason": result.reject_reason})
    return json.dumps({"actions": [_command_to_dict(c) for c in result.commands]})


def _command_to_dict(c) -> Dict:
    if isinstance(c, MoveCommand):
        return {"action": "move", "vx": c.vx, "vy": c.vy, "wz": c.wz,
                "duration": c.duration}
    if isinstance(c, TurnCommand):
        return {"action": "turn", "angle_deg": c.angle_deg}
    if isinstance(c, GotoObjectCommand):
        return {"action": "goto_object", "class": c.object_class,
                "color": c.color}
    if isinstance(c, StopCommand):
        return {"action": "stop"}
    if isinstance(c, ChatCommand):
        return {"action": "chat", "reply": c.reply}
    if isinstance(c, LookCommand):
        return {"action": "look", "question": c.question}
    raise TypeError(f"unknown command {c!r}")


_FENCE_RE = re.compile(r"^\s*```(?:json|JSON)?\s*\n?(.*?)\n?\s*```\s*$", re.S)


def _strip_fences(raw: str) -> str:
    m = _FENCE_RE.match(raw or "")
    return m.group(1) if m else (raw or "")


def _to_parse_result(raw_json: str) -> ParseResult:
    try:
        data = json.loads(_strip_fences(raw_json))
    except (json.JSONDecodeError, TypeError):
        return _reject("malformed_json")

    try:
        if isinstance(data, dict) and data.get("rejected"):
            return _reject(_clean_reason(data.get("reason")))
        if isinstance(data, list):
            actions = data
        elif isinstance(data, dict) and "actions" in data:
            actions = data["actions"]
        elif isinstance(data, dict) and "action" in data:
            actions = [data]   # one bare action object, e.g. {"action": "stop"}
        else:
            raise _Invalid("invalid_field:actions")
        if not isinstance(actions, list):
            raise _Invalid("invalid_field:actions")
        if not actions:
            raise _Invalid("empty_actions")
        commands = [_to_command(a) for a in actions]
    except _Invalid as e:
        return _reject(e.args[0])

    summary = ", ".join(_describe(c) for c in commands)
    print(f"[CMD] actions={summary} n={len(commands)}")
    return ParseResult(accepted=True, commands=commands)


def _to_command(a):
    if not isinstance(a, dict):
        raise _Invalid("invalid_field:action")
    kind = a.get("action")
    if not isinstance(kind, str):
        raise _Invalid("invalid_field:action")
    if kind == "move":
        vx = _number(a, "vx", -1.0, 1.0)
        vy = _number(a, "vy", -1.0, 1.0)
        wz = _number(a, "wz", -1.0, 1.0)
        duration = _number(a, "duration", 0.0, MAX_DURATION_S)
        if duration <= 0.0:
            raise _Invalid("invalid_field:duration")
        return MoveCommand(vx, vy, wz, duration)
    if kind == "turn":
        return TurnCommand(_number(a, "angle_deg"))
    if kind == "goto_object":
        cls = _string(a, "class").strip().lower()
        color = _string(a, "color", allow_empty=True).strip().lower()
        if cls not in COCO_CLASSES:
            raise _Invalid(f"unknown_class:{cls}")
        if not color:
            # navigation needs an exact colour match, so ask instead of
            # sending the robot on a search that can't succeed.
            return ChatCommand(f"Which {cls} do you mean? Please tell me its colour.")
        return GotoObjectCommand(cls, color)
    if kind == "stop":
        return StopCommand()
    if kind == "chat":
        return ChatCommand(_string(a, "reply").strip())
    if kind == "look":
        question = _string(a, "question").strip()
        if len(question) > MAX_LOOK_QUESTION_CHARS:
            raise _Invalid("invalid_field:question")
        return LookCommand(question)
    raise _Invalid(f"unknown_action:{kind}")


def _number(a: Dict, name: str, lo: Optional[float] = None,
            hi: Optional[float] = None) -> float:
    v = a.get(name)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise _Invalid(f"invalid_field:{name}")
    v = float(v)
    if not math.isfinite(v):
        raise _Invalid(f"invalid_field:{name}")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise _Invalid(f"invalid_field:{name}")
    return v


def _string(a: Dict, name: str, allow_empty: bool = False) -> str:
    v = a.get(name)
    if not isinstance(v, str) or (not allow_empty and not v.strip()):
        raise _Invalid(f"invalid_field:{name}")
    return v


def _clean_reason(reason) -> str:
    if not isinstance(reason, str) or not reason.strip():
        return "unspecified"
    return "_".join(reason.split())[:80]


def _reject(reason: str) -> ParseResult:
    print(f"[CMD] rejected reason={reason}")
    return ParseResult(accepted=False, reject_reason=reason)


def _fmt(x: float) -> str:
    return f"{x:g}"


def _describe(c) -> str:
    if isinstance(c, MoveCommand):
        extra = "".join(f", {k}={_fmt(v)}" for k, v in (("vy", c.vy), ("wz", c.wz)) if v)
        return f"move(vx={_fmt(c.vx)}{extra}, {c.duration:.1f} s)"
    if isinstance(c, TurnCommand):
        return f"turn({_fmt(c.angle_deg)} deg)"
    if isinstance(c, GotoObjectCommand):
        return f"goto_object(class={c.object_class}, color={c.color})"
    if isinstance(c, StopCommand):
        return "stop"
    if isinstance(c, ChatCommand):
        return "chat"
    if isinstance(c, LookCommand):
        return f'look("{c.question}")'
    return str(c)
