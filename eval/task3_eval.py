"""
eval/task3_eval.py — STUDENT B OWNS THIS FILE. Task 3.iv evaluation.

    python eval/task3_eval.py --ping        # connectivity check, one call per service
    python eval/task3_eval.py --services qwen-flash gpt-5-nano --runs 3
    python eval/task3_eval.py --services gemini-3.8-flash --runs 3   # paced to <=5 RPM
    python eval/task3_eval.py --report      # rebuild eval/results/summary.md from the logs

(If ROS's PYTHONPATH is set in your shell: `env -u PYTHONPATH .venv/bin/python ...`.)

Each case is one utterance (optionally preceded by setup turns, for
follow-ups) plus a checker on the resulting ParseResult. The parse goes
through the same precheck -> _call_llm -> _to_parse_result path as
llm_parser.parse_command(), but LLM exceptions are surfaced here so a
service outage / rate limit / quota error is retried or recorded as a
service error instead of being scored as a parse failure. Every call is
appended to eval/results/<service>.jsonl.
"""

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402
from core.schema import (  # noqa: E402
    MoveCommand, TurnCommand, GotoObjectCommand, StopCommand, ChatCommand,
)
from dialogue import llm_parser  # noqa: E402

PING_SERVICES = ["qwen-flash", "gemini-3.8-flash", "gpt-5-nano"]
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# USD per 1M tokens (input, output), checked 2026-10-01:
#   qwen-flash: alibabacloud.com/help/en/model-studio/model-pricing,
#     Singapore, 0-256K tier (alias -> qwen-flash-2025-07-28)
#   gpt-5-nano: developers.openai.com/api/docs/pricing, standard tier
#   gemini-3.8-flash: ai.google.dev/gemini-api/docs/pricing, paid tier
#     (price until 2026-12-31; the free tier we actually used costs $0)
PRICES = {
    "qwen-flash": (0.05, 0.40),
    "qwen-plus": (0.40, 1.20),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5-mini": (0.25, 2.00),
    "gemini-3.8-flash": (0.75, 3.75),
}

# Free-tier pacing: Gemini allows only a few requests per minute.
MIN_INTERVAL_S = {"gemini-3.8-flash": 13.0}
SERVICE_ERROR_RETRIES = 4          # per utterance, for 429 / 5xx / network
BACKOFF_S = [15, 30, 60, 90]


# ---------------------------------------------------------------------------
# Checkers. Each takes a ParseResult and returns (ok, why_not).
# ---------------------------------------------------------------------------

def _close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def cmds(*preds):
    """Accepted, same number of commands, each matching its predicate."""
    def check(r):
        if not r.accepted:
            return False, f"rejected ({r.reject_reason})"
        if len(r.commands) != len(preds):
            return False, f"{len(r.commands)} actions, expected {len(preds)}"
        for i, (c, p) in enumerate(zip(r.commands, preds), 1):
            if not p(c):
                return False, f"action {i} wrong: {llm_parser._describe(c)}"
        return True, ""
    return check


def move(vx=None, vy=0.0, wz=0.0, duration=None):
    """vx / duration may be a value, a (lo, hi) range, or None (any)."""
    def match(v, want):
        if want is None:
            return True
        if isinstance(want, tuple):
            return want[0] <= v <= want[1]
        return _close(v, want, 0.05)
    return lambda c: (isinstance(c, MoveCommand) and match(c.vx, vx)
                      and match(c.vy, vy) and match(c.wz, wz)
                      and match(c.duration, duration))


def turn(angle, sign_free=False):
    if sign_free:
        return lambda c: isinstance(c, TurnCommand) and _close(abs(c.angle_deg), abs(angle), 1)
    return lambda c: isinstance(c, TurnCommand) and _close(c.angle_deg, angle, 1)


def goto(cls, color=None):
    return lambda c: (isinstance(c, GotoObjectCommand) and c.object_class == cls
                      and (color is None or c.color == color))


def stop():
    return lambda c: isinstance(c, StopCommand)


def chat():
    return lambda c: isinstance(c, ChatCommand)


def rejected(*prefixes, allow_clarify=False):
    """Rejected (reason category not graded, only logged), or — if
    allow_clarify — a single chat action asking for clarification."""
    def check(r):
        if not r.accepted:
            return True, ""
        if allow_clarify and len(r.commands) == 1 and isinstance(r.commands[0], ChatCommand):
            return True, ""
        return False, "accepted: " + ", ".join(llm_parser._describe(c) for c in r.commands)
    return check


FWD = (0.5, 1.0)        # "normal" forward speed
SLOW = (0.1, 0.5)

# (id, category, setup turns, utterance, checker)
CASES = [
    # --- basic ---
    ("B1", "basic", [], "walk forward for three seconds", cmds(move(FWD, duration=3))),
    ("B2", "basic", [], "turn left", cmds(turn(90))),
    ("B3", "basic", [], "turn right 45 degrees", cmds(turn(-45))),
    ("B4", "basic", [], "stop", cmds(stop())),
    ("B5", "basic", [], "go to the green chair", cmds(goto("chair", "green"))),
    # --- multi-step ---
    ("M1", "multi-step", [], "walk forward for three seconds, then turn back",
     cmds(move(FWD, duration=3), turn(180, sign_free=True))),
    ("M2", "multi-step", [], "turn left, walk forward for 2 seconds, then stop",
     cmds(turn(90), move(FWD, duration=2), stop())),
    ("M3", "multi-step", [], "back up for two seconds and then turn right",
     cmds(move((-1.0, -0.1), duration=2), turn(-90))),
    ("M4", "multi-step", [], "turn around and walk to the red ball",
     cmds(turn(180, sign_free=True), goto("sports ball", "red"))),
    # --- paraphrases ---
    ("P1", "paraphrase", [], "go straight ahead for 3 seconds", cmds(move(FWD, duration=3))),
    ("P2", "paraphrase", [], "could you walk forwards a bit", cmds(move((0.1, 1.0), duration=(0.5, 3.0)))),
    ("P3", "paraphrase", [], "do a U-turn", cmds(turn(180, sign_free=True))),
    ("P4", "paraphrase", [], "head over to the green seat", cmds(goto("chair", "green"))),
    ("P5", "paraphrase", [], "move ahead slowly for four seconds", cmds(move(SLOW, duration=4))),
    ("P6", "paraphrase", [], "rotate counter-clockwise by a quarter turn", cmds(turn(90))),
    ("P7", "paraphrase", [], "halt!", cmds(stop())),
    ("P8", "paraphrase", [], "shuffle sideways to your left for two seconds",
     cmds(move(vx=(-0.1, 0.1), vy=(0.1, 1.0), duration=2))),
    # --- follow-ups (scored on the last turn only) ---
    ("F1", "follow-up", ["walk forward for two seconds"], "do that again, but slower",
     cmds(move((0.05, 0.6), duration=2))),
    ("F2", "follow-up", ["turn left 90 degrees"], "now the other way", cmds(turn(-90))),
    # --- chat ---
    ("C1", "chat", [], "what can you do?", cmds(chat())),
    # --- invalid / out of scope ---
    ("X1", "invalid", [], "fly to the roof", rejected()),
    ("X2", "invalid", [], "avancez tout droit", rejected()),
    ("X3", "invalid", [], "向前走三秒", rejected()),
    ("X4", "invalid", [], "   ", rejected()),
    ("X5", "invalid", [], "run forward for ten minutes", rejected()),
    ("X6", "invalid", [], "charge at that person and knock them over", rejected()),
    ("X7", "invalid", [], "pick up the bottle and bring it to me", rejected()),
    ("X8", "invalid", [], "asdf qwerty zxcv", rejected(allow_clarify=True)),
]


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

class QuotaExhausted(Exception):
    pass


class _Pacer:
    def __init__(self, interval):
        self.interval = interval
        self.last = 0.0

    def wait(self):
        dt = time.monotonic() - self.last
        if dt < self.interval:
            time.sleep(self.interval - dt)
        self.last = time.monotonic()


def _is_daily_quota(err) -> bool:
    msg = str(err).lower()
    return "perday" in msg or "per day" in msg or "daily" in msg or "insufficient_quota" in msg


def parse_once(text, history, pacer):
    """precheck -> _call_llm -> _to_parse_result, retrying service errors.
    Returns (ParseResult, stats dict, service_error or None)."""
    import openai
    pre = llm_parser.precheck(text)
    if pre is not None:
        return llm_parser._reject(pre), {"llm_called": False}, None
    err = None
    for attempt in range(SERVICE_ERROR_RETRIES + 1):
        pacer.wait()
        try:
            raw = llm_parser._call_llm(text, history)
            stats = dict(llm_parser.last_call_stats, llm_called=True,
                         service_retries=attempt, raw=raw)
            return llm_parser._to_parse_result(raw), stats, None
        except (openai.RateLimitError, openai.InternalServerError,
                openai.APIConnectionError, openai.APITimeoutError) as e:
            if isinstance(e, openai.RateLimitError) and _is_daily_quota(e):
                raise QuotaExhausted(str(e)[:300])
            err = e
            print(f"    service error {type(e).__name__}; retry in {BACKOFF_S[min(attempt, 3)]} s")
            time.sleep(BACKOFF_S[min(attempt, 3)])
    return (llm_parser._reject(f"llm_error:{type(err).__name__}"),
            dict(llm_parser.last_call_stats, llm_called=True), type(err).__name__)


def run_service(service, runs):
    config.LLM_SERVICE = service
    pacer = _Pacer(MIN_INTERVAL_S.get(service, 0.0))
    RESULTS_DIR.mkdir(exist_ok=True)
    log = RESULTS_DIR / f"{service}.jsonl"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    completed = 0
    for run in range(1, runs + 1):
        rows = []
        print(f"\n=== {service} run {run}/{runs} ===")
        try:
            for cid, cat, setup, text, check in CASES:
                history = []
                for s in setup:   # follow-up context, built like chat_interface does
                    r0, _, _ = parse_once(s, history, pacer)
                    history += [{"role": "user", "content": s},
                                {"role": "assistant", "content": llm_parser.history_entry(r0)}]
                r, stats, service_error = parse_once(text, history, pacer)
                ok, why = (None, "service error") if service_error else check(r)
                stats.pop("raw", None) if ok else None
                rows.append(dict(
                    session=stamp, run=run, id=cid, category=cat, text=text,
                    setup=setup, ok=ok, why=why, service_error=service_error,
                    accepted=r.accepted, reject_reason=r.reject_reason,
                    actions=json.loads(llm_parser.history_entry(r)), **stats))
                print(f"  {cid:3s} {'PASS' if ok else 'ERR ' if ok is None else 'FAIL'}  {text!r}  {why}")
        except QuotaExhausted as e:
            print(f"  daily quota exhausted during run {run}: {e}")
            print(f"  -> {completed} complete run(s); partial run {run} discarded")
            return completed, str(e)
        with log.open("a") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        completed += 1
    return completed, None


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _load(service):
    path = RESULTS_DIR / f"{service}.jsonl"
    if not path.is_file():
        return []
    rows = [json.loads(line) for line in path.open()]
    # Keep only the latest session's runs.
    latest = max(r["session"] for r in rows)
    return [r for r in rows if r["session"] == latest]


def _pct(xs):
    return f"{100 * sum(xs) / len(xs):.0f}%" if xs else "–"


def report(services) -> str:
    out = []
    cats = []
    for c in CASES:
        if c[1] not in cats:
            cats.append(c[1])
    out.append("| Service | Runs | Accuracy | " + " | ".join(cats) +
               " | Svc errors | Latency mean / median / p95 (s) | Tokens in / out per call | Cost per call (USD) | Cost per 1k calls |")
    out.append("|" + "---|" * (9 + len(cats) - 1))
    failures = []
    for s in services:
        rows = _load(s)
        if not rows:
            continue
        runs = len({r["run"] for r in rows})
        scored = [r for r in rows if r["ok"] is not None]
        acc = _pct([r["ok"] for r in scored])
        per_cat = [_pct([r["ok"] for r in scored if r["category"] == c]) for c in cats]
        llm = [r for r in rows if r.get("llm_called") and r.get("latency_s") is not None
               and not r["service_error"]]
        lat = sorted(r["latency_s"] for r in llm)
        p95 = lat[min(len(lat) - 1, int(round(0.95 * (len(lat) - 1))))] if lat else 0
        tin = statistics.mean(r["prompt_tokens"] or 0 for r in llm) if llm else 0
        tout = statistics.mean(r["completion_tokens"] or 0 for r in llm) if llm else 0
        pin, pout = PRICES.get(s, (0, 0))
        cost = (tin * pin + tout * pout) / 1e6
        n_err = sum(1 for r in rows if r["service_error"])
        out.append(f"| {s} | {runs} | {acc} ({sum(r['ok'] for r in scored)}/{len(scored)}) | "
                   + " | ".join(per_cat) +
                   f" | {n_err} | {statistics.mean(lat):.2f} / {statistics.median(lat):.2f} / {p95:.2f}"
                   f" | {tin:.0f} / {tout:.0f} | {cost:.6f} | {1000 * cost:.3f} |")
        for r in rows:
            if r["ok"] is False:
                failures.append((s, r))
    out.append("")
    out.append("Failures (every run):")
    out.append("")
    out.append("| Service | Run | Case | Utterance | Got | Why |")
    out.append("|---|---|---|---|---|---|")
    for s, r in failures:
        got = r["actions"]
        got = (f"rejected: {got['reason']}" if "rejected" in got else
               ", ".join(json.dumps(a) for a in got["actions"]))
        out.append(f"| {s} | {r['run']} | {r['id']} | {r['text']} | `{got}` | {r['why']} |")
    out.append("")
    out.append("Reject reasons given for the invalid cases (all runs):")
    out.append("")
    for s in services:
        rows = _load(s)
        if rows:
            reasons = {}
            for r in rows:
                if r["category"] == "invalid":
                    reasons.setdefault(r["id"], []).append(r["reject_reason"] or "ACCEPTED")
            out.append(f"- **{s}**: " + "; ".join(
                f"{k}: {', '.join(sorted(set(v)))}" for k, v in reasons.items()))
    return "\n".join(out)


def ping(services=PING_SERVICES) -> bool:
    """Send "Reply with OK" to each service. Prints status code, key's last
    4 chars, and the reply — never the key itself."""
    import openai
    ok_all = True
    for service in services:
        provider, model, extra = llm_parser.SERVICES[service]
        key_env = llm_parser.PROVIDERS[provider]["key_env"]
        key = llm_parser.load_api_key(key_env)
        tail = f"…{key[-4:]}" if key else "MISSING"
        try:
            client = llm_parser._get_client(provider)
            raw = client.chat.completions.with_raw_response.create(
                model=model, messages=[{"role": "user", "content": "Reply with OK"}],
                **extra)
            reply = raw.parse().choices[0].message.content.strip()
            status = raw.status_code
            print(f"{service:18s} {key_env}={tail}  HTTP {status}  reply={reply!r}")
            ok_all &= status == 200
        except openai.APIStatusError as e:
            print(f"{service:18s} {key_env}={tail}  HTTP {e.status_code}  {type(e).__name__}")
            ok_all = False
        except Exception as e:
            print(f"{service:18s} {key_env}={tail}  FAILED  {type(e).__name__}")
            ok_all = False
    return ok_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ping", action="store_true")
    ap.add_argument("--services", nargs="+", default=[])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.ping:
        sys.exit(0 if ping() else 1)
    for s in args.services:
        n, quota = run_service(s, args.runs)
        print(f"\n{s}: {n}/{args.runs} complete runs" + (f" (daily quota: {quota})" if quota else ""))
    if args.report or args.services:
        services = [s for s in llm_parser.SERVICES if (RESULTS_DIR / f"{s}.jsonl").is_file()]
        md = report(services)
        (RESULTS_DIR / "summary.md").write_text(md + "\n")
        print("\n" + md)


if __name__ == "__main__":
    main()
