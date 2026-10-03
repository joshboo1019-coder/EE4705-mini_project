"""
eval/ablation.py — STUDENT B OWNS THIS FILE. Structured-output ablation.

Same prompt (v5), same 33 v3 cases (eval/task3_eval.CASES minus look and
multi-goal), same validator; only the way the JSON is requested changes:

  json_object  response_format={"type": "json_object"}   (what the robot uses)
  json_schema  response_format={"type": "json_schema", strict}: the v5
               action grammar as a JSON Schema (recursive for programs)
  tools        function calling: one function `robot_command` whose
               parameters are that schema, forced with tool_choice

    eval/run_env.sh eval/ablation.py --services qwen-flash gpt-5-nano --modes json_schema tools --budget 0.05

Rows go to eval/results/ablation/<mode>/<service>.jsonl. A mode the
endpoint rejects (HTTP 400) is recorded as unsupported, not as a parse
failure.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402
from dialogue import llm_parser  # noqa: E402
from eval import task3_eval as t3  # noqa: E402

V3_IDS = [c[0] for c in t3.CASES if c[1] not in ("look", "multi-goal")]
OUT = t3.RESULTS_DIR / "ablation"


def _obj(props, required=None):
    return {"type": "object", "properties": props, "required": required or list(props),
            "additionalProperties": False}


def _const(name):
    return {"type": "string", "enum": [name]}


NUM = {"type": "number"}
STR = {"type": "string"}
ACTION_REF = {"$ref": "#/$defs/action"}

SCHEMA = _obj({
    "rejected": {"type": "boolean"},
    "reason": {"type": ["string", "null"]},
    "suggestion": {"type": ["string", "null"]},
    "actions": {"type": "array", "items": ACTION_REF},
})
SCHEMA["$defs"] = {"action": {"anyOf": [
    _obj({"action": _const("move"), "vx": NUM, "vy": NUM, "wz": NUM, "duration": NUM}),
    _obj({"action": _const("move"), "vx": NUM, "vy": NUM, "wz": NUM, "distance_m": NUM}),
    _obj({"action": _const("turn"), "angle_deg": NUM}),
    _obj({"action": _const("goto_object"), "class": STR, "color": STR}),
    _obj({"action": _const("stop")}),
    _obj({"action": _const("chat"), "reply": STR}),
    _obj({"action": _const("look"), "question": STR}),
    _obj({"action": _const("repeat"), "times": {"type": "integer"},
          "actions": {"type": "array", "items": ACTION_REF}}),
    _obj({"action": _const("until_see"), "class": STR, "color": STR,
          "do": {"type": "array", "items": ACTION_REF}, "max_iter": {"type": "integer"}}),
    _obj({"action": _const("status"),
          "topic": {"type": "string", "enum": ["last_action", "home", "last_reject", "seen"]}}),
    _obj({"action": _const("undo")}),
    _obj({"action": _const("return_home")}),
]}}

MODE_NOTE = ("\nThe output format is enforced by the API: always fill every field; use "
             "\"rejected\": false, \"reason\": null, \"suggestion\": null when you return actions, "
             "and \"actions\": [] when you reject.")


def _schema_format():
    return {"type": "json_schema",
            "json_schema": {"name": "robot_command", "strict": True, "schema": SCHEMA}}


def _request(text, history, snapshot, **kw):
    """One request like llm_parser._call_llm (same messages, same extra
    params, stats in last_call_stats) but WITHOUT its fallback that drops
    a rejected parameter: an unsupported mode must fail loudly here."""
    service = config.LLM_SERVICE
    provider, model, extra = llm_parser.SERVICES[service]
    client = llm_parser._get_client(provider)
    messages = [{"role": "system", "content": llm_parser.SYSTEM_PROMPT}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": llm_parser.user_message(text, snapshot)})
    stats = llm_parser.last_call_stats
    stats.clear()
    stats.update(service=service, model=model, latency_s=None, prompt_tokens=None,
                 completion_tokens=None, attempts=1, error=None)
    t0 = time.perf_counter()
    try:
        resp = client.chat.completions.create(model=model, messages=messages, **dict(extra), **kw)
    except Exception as e:
        stats.update(latency_s=time.perf_counter() - t0, error=type(e).__name__)
        raise
    usage = getattr(resp, "usage", None)
    stats.update(latency_s=time.perf_counter() - t0,
                 prompt_tokens=getattr(usage, "prompt_tokens", None),
                 completion_tokens=getattr(usage, "completion_tokens", None))
    return resp.choices[0].message


def call_tools(text, history, snapshot):
    """Function calling: one forced tool whose parameters are SCHEMA."""
    tool = {"type": "function", "function": {
        "name": "robot_command", "description": "The parsed robot command (or a rejection).",
        "parameters": SCHEMA, "strict": True}}
    msg = _request(text, history, snapshot, tools=[tool],
                   tool_choice={"type": "function", "function": {"name": "robot_command"}})
    calls = getattr(msg, "tool_calls", None) or []
    return calls[0].function.arguments if calls else (msg.content or "")


def call_schema(text, history, snapshot):
    return _request(text, history, snapshot, response_format=_schema_format()).content or ""


def run(service, mode, spend):
    import openai
    config.LLM_SERVICE = service
    base = t3.PROMPTS["v5"]
    llm_parser.SYSTEM_PROMPT = base + (MODE_NOTE if mode != "json_object" else "")
    call = {"json_object": None, "json_schema": call_schema, "tools": call_tools}[mode]
    cases = [c for c in t3.CASES if c[0] in V3_IDS]
    pacer = t3._Pacer(0.0)
    out_dir = OUT / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rows = []
    print(f"\n=== ablation {service} {mode} ({len(cases)} cases) ===")
    for cid, cat, setup, text, check in cases:
        history, setup_cost = [], 0.0
        try:
            for s in setup:
                r0, st0, _ = t3.parse_once(s, history, pacer, spend, call=call)
                setup_cost += st0.get("cost_usd", 0.0)
                history += [{"role": "user", "content": s},
                            {"role": "assistant", "content": llm_parser.history_entry(r0)}]
            r, stats, api_error = t3.parse_once(text, history, pacer, spend, call=call)
        except openai.BadRequestError as e:
            print(f"  {mode} unsupported on {service}: {str(e)[:300]}")
            rows.append(dict(session=stamp, mode=mode, service=service, unsupported=str(e)[:500]))
            break
        ok, why = (None, "API error") if api_error else check(r)
        rows.append(dict(session=stamp, mode=mode, id=cid, category=cat, text=text, ok=ok, why=why,
                         api_error=api_error, accepted=r.accepted, reject_reason=r.reject_reason,
                         actions=json.loads(llm_parser.history_entry(r)),
                         setup_cost_usd=setup_cost, **stats))
        print(f"  {cid:3s} {'PASS' if ok else 'APIE' if ok is None else 'FAIL'}  {text!r}  {why}")
    with (out_dir / f"{service}.jsonl").open("a") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--services", nargs="+", default=["qwen-flash", "gpt-5-nano"])
    ap.add_argument("--modes", nargs="+", default=["json_schema", "tools"],
                    choices=["json_object", "json_schema", "tools"])
    ap.add_argument("--budget", type=float, default=0.05)
    args = ap.parse_args()
    spend = t3._Spend(args.budget)
    try:
        for mode in args.modes:
            for s in args.services:
                run(s, mode, spend)
    finally:
        for s, usd in spend.usd.items():
            print(f"TOTAL estimated spend {s}: ${usd:.4f} over {spend.calls[s]} calls")


if __name__ == "__main__":
    main()
