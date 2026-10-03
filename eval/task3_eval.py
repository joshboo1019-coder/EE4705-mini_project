"""
eval/task3_eval.py — STUDENT B OWNS THIS FILE. Task 3.iv evaluation.

    python eval/task3_eval.py --ping [SERVICE ...]   # connectivity check, one call per service
    python eval/task3_eval.py --services qwen-flash gpt-5-nano --prompt v1 v2 --runs 3
    python eval/task3_eval.py --services gemini-3.8-flash --prompt v1 v2 --budget 2  # paced to <=5 RPM
    python eval/task3_eval.py --services qwen-flash --prompt v1 --cases L1 L2 L3     # add cases to old runs
    python eval/task3_eval.py --report      # rebuild eval/results/summary.md from the logs

--prompt v1 / v2 / v3 are the frozen prompts in eval/prompt_v1.py ... prompt_v3.py;
v4 is the current llm_parser.SYSTEM_PROMPT.

(If ROS's PYTHONPATH is set in your shell: `env -u PYTHONPATH .venv/bin/python ...`.)

Each case is one utterance (optionally preceded by setup turns, for
follow-ups) plus a checker on the resulting ParseResult. The parse goes
through the same precheck -> _call_llm -> _to_parse_result path as
llm_parser.parse_command(), but LLM exceptions are surfaced here so a
service outage / rate limit / quota error is retried or recorded as a
service error instead of being scored as a parse failure. Every call is
appended to eval/results/<prompt>/<service>.jsonl.
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
from eval.prompt_v1 import SYSTEM_PROMPT_V1  # noqa: E402
from eval.prompt_v2 import SYSTEM_PROMPT_V2  # noqa: E402
from eval.prompt_v3 import SYSTEM_PROMPT_V3  # noqa: E402
from dialogue.commands import LookCommand  # noqa: E402

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
API_ERROR_RETRIES = 5              # per utterance, for 429 / 5xx / network
BACKOFF_BASE_S = 5                 # exponential: 5, 10, 20, 40, 80 s


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


def look():
    return lambda c: isinstance(c, LookCommand) and bool(c.question.strip())


def no_look():
    """Anything (accepted or rejected) as long as no look action is produced."""
    def check(r):
        if any(isinstance(c, LookCommand) for c in r.commands):
            return False, "produced a look action"
        return True, ""
    return check


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
    # --- lateral (added with prompt v2; none is a copy of a few-shot example) ---
    ("L1", "lateral", [], "sidestep to your left for two seconds",
     cmds(move(vx=(-0.1, 0.1), vy=(0.1, 1.0), duration=2))),
    ("L2", "lateral", [], "shuffle right for one second",
     cmds(move(vx=(-0.1, 0.1), vy=(-1.0, -0.1), duration=1))),
    ("L3", "lateral", [], "slide over to the right a little",
     cmds(move(vx=(-0.1, 0.1), vy=(-1.0, -0.1), duration=(0.5, 3.0)))),
    # --- follow-ups (scored on the last turn only) ---
    ("F1", "follow-up", ["walk forward for two seconds"], "do that again, but slower",
     cmds(move((0.05, 0.6), duration=2))),
    ("F2", "follow-up", ["turn left 90 degrees"], "now the other way", cmds(turn(-90))),
    ("F3", "follow-up", ["go to the chair"], "the green one", cmds(goto("chair", "green"))),
    # --- chat ---
    ("C1", "chat", [], "what can you do?", cmds(chat())),
    # no colour given: navigation needs one, so the robot must ask which chair
    ("C2", "chat", [], "go to the chair", cmds(chat())),
    # --- look / visual QA (added with prompt v4; none copies a v4 few-shot example) ---
    ("V1", "look", [], "what can you see?", cmds(look())),
    ("V2", "look", [], "is there a chair in front of you?", cmds(look())),
    ("V3", "look", [], "what colour is the ball ahead?", cmds(look())),
    ("V4", "look", [], "describe your surroundings", cmds(look())),
    ("V5", "look", [], "look out!", no_look()),          # a warning, not a question
    # held-out warnings (added after v4 was frozen; none appears in the prompt)
    ("V6", "look", [], "watch out!", no_look()),
    ("V7", "look", [], "heads up, there's a wall", no_look()),
    ("V8", "look", [], "careful, stop there", no_look()),
    # --- multi-goal missions (Part 3; added after v4 was frozen, none is a prompt example) ---
    ("G1", "multi-goal", [], "go to the orange ball, then the green chair",
     cmds(goto("sports ball", "orange"), goto("chair", "green"))),
    ("G2", "multi-goal", [], "visit the red chair, the green chair and then the orange ball",
     cmds(goto("chair", "red"), goto("chair", "green"), goto("sports ball", "orange"))),
    ("G3", "multi-goal", [], "first find the green chair and after that go to the red one",
     cmds(goto("chair", "green"), goto("chair", "red"))),
    ("G4", "multi-goal", [], "go to the green chair, then turn around and go to the orange ball",
     cmds(goto("chair", "green"), turn(180, sign_free=True), goto("sports ball", "orange"))),
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

PROMPTS = {"v1": SYSTEM_PROMPT_V1, "v2": SYSTEM_PROMPT_V2, "v3": SYSTEM_PROMPT_V3,
           "v4": llm_parser.SYSTEM_PROMPT}


class QuotaExhausted(Exception):
    pass


class BudgetExceeded(Exception):
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


class _Spend:
    """Running cost estimate (from token counts) per service, over every
    LLM call this process makes — scored calls and follow-up setup turns."""
    def __init__(self, budget):
        self.budget = budget
        self.usd = {}
        self.calls = {}

    def add(self, service, stats):
        cost = call_cost(service, stats.get("prompt_tokens"), stats.get("completion_tokens"))
        self.usd[service] = self.usd.get(service, 0.0) + cost
        self.calls[service] = self.calls.get(service, 0) + 1
        if self.budget is not None and self.usd[service] > self.budget:
            raise BudgetExceeded(f"{service} spend ${self.usd[service]:.4f} > ${self.budget}")
        return cost


def call_cost(service, tin, tout):
    pin, pout = PRICES.get(service, (0.0, 0.0))
    return ((tin or 0) * pin + (tout or 0) * pout) / 1e6


def _quota_kind(err):
    """'free_tier' / 'daily' for quota errors that retrying won't fix."""
    msg = str(err).lower()
    if "freetier" in msg or "free_tier" in msg:
        return "free_tier"
    if "perday" in msg or "per day" in msg or "insufficient_quota" in msg:
        return "daily"
    return None


def parse_once(text, history, pacer, spend):
    """precheck -> _call_llm -> _to_parse_result, retrying 429/5xx/network
    errors with exponential back-off. Returns (ParseResult, stats,
    api_error or None); an api_error is NOT a parse error."""
    import openai
    pre = llm_parser.precheck(text)
    if pre is not None:
        return llm_parser._reject(pre), {"llm_called": False}, None
    err = None
    for attempt in range(API_ERROR_RETRIES + 1):
        pacer.wait()
        try:
            raw = llm_parser._call_llm(text, history)
        except (openai.RateLimitError, openai.InternalServerError,
                openai.APIConnectionError, openai.APITimeoutError) as e:
            if isinstance(e, openai.RateLimitError) and _quota_kind(e):
                raise QuotaExhausted(f"{_quota_kind(e)}: {str(e)[:400]}")
            err = e
            delay = BACKOFF_BASE_S * 2 ** attempt
            if attempt < API_ERROR_RETRIES:
                print(f"    API error {type(e).__name__}; retry in {delay:.0f} s")
                time.sleep(delay)
            continue
        stats = dict(llm_parser.last_call_stats, llm_called=True,
                     api_retries=attempt, raw=raw)
        stats["cost_usd"] = spend.add(config.LLM_SERVICE, stats)
        return llm_parser._to_parse_result(raw), stats, None
    return (llm_parser._reject(f"llm_error:{type(err).__name__}"),
            dict(llm_parser.last_call_stats, llm_called=True,
                 api_retries=API_ERROR_RETRIES), type(err).__name__)


def run_service(service, prompt, runs, case_ids, spend):
    config.LLM_SERVICE = service
    llm_parser.SYSTEM_PROMPT = PROMPTS[prompt]
    cases = [c for c in CASES if not case_ids or c[0] in case_ids]
    pacer = _Pacer(MIN_INTERVAL_S.get(service, 0.0))
    out_dir = RESULTS_DIR / prompt
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / f"{service}.jsonl"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    completed = 0
    for run in range(1, runs + 1):
        rows = []
        print(f"\n=== {service} prompt {prompt} run {run}/{runs} ({len(cases)} cases) ===")
        try:
            for cid, cat, setup, text, check in cases:
                history, setup_cost = [], 0.0
                for s in setup:   # follow-up context, built like chat_interface does
                    r0, st0, _ = parse_once(s, history, pacer, spend)
                    setup_cost += st0.get("cost_usd", 0.0)
                    history += [{"role": "user", "content": s},
                                {"role": "assistant", "content": llm_parser.history_entry(r0)}]
                r, stats, api_error = parse_once(text, history, pacer, spend)
                ok, why = (None, "API error") if api_error else check(r)
                if ok:
                    stats.pop("raw", None)
                rows.append(dict(
                    session=stamp, prompt=prompt, run=run, id=cid, category=cat,
                    text=text, setup=setup, ok=ok, why=why, api_error=api_error,
                    accepted=r.accepted, reject_reason=r.reject_reason,
                    actions=json.loads(llm_parser.history_entry(r)),
                    setup_cost_usd=setup_cost, **stats))
                print(f"  {cid:3s} {'PASS' if ok else 'APIE' if ok is None else 'FAIL'}  {text!r}  {why}")
        except (QuotaExhausted, BudgetExceeded) as e:
            print(f"  STOPPED during run {run}: {type(e).__name__}: {e}")
            print(f"  -> {completed} complete run(s); partial run {run} discarded")
            raise
        with log.open("a") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        completed += 1
        print(f"  spend so far: {service} ${spend.usd.get(service, 0):.4f} "
              f"over {spend.calls.get(service, 0)} calls")
    return completed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def load(prompt, service):
    """All logged rows for (prompt, service), latest row per (run, case),
    restricted to the current CASES — so cases added later can be run on
    their own (--cases) and merged with earlier runs of the other cases."""
    path = RESULTS_DIR / prompt / f"{service}.jsonl"
    if not path.is_file():
        return []
    ids = {c[0] for c in CASES}
    latest = {}
    for line in path.open():
        r = json.loads(line)
        r.setdefault("api_error", r.get("service_error"))
        if r["id"] in ids:
            latest[(r["run"], r["id"])] = r
    return sorted(latest.values(), key=lambda r: (r["run"], r["id"]))


def _acc(rows):
    scored = [r for r in rows if r["ok"] is not None]
    if not scored:
        return "–"
    k = sum(r["ok"] for r in scored)
    return f"{100 * k / len(scored):.1f}% ({k}/{len(scored)})"


def _quantile(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else float("nan")


def _got(r):
    a = r["actions"]
    return (f"rejected: {a['reason']}" if "rejected" in a else
            ", ".join(json.dumps(x) for x in a["actions"]))


def report(services, prompts=("v1", "v2", "v3", "v4")) -> str:
    out = [f"Test set: {len(CASES)} utterances; each prompt is scored on the cases it was run on "
           "(C2 and F3 were added with v3, V1-V5 with v4, held-out V6-V8 and multi-goal G1-G4 after v4 was frozen; v1/v2 cover 31, v3 33). Accuracy excludes API errors "
           "(calls that still failed after back-off), which are counted separately.", ""]
    for prompt in prompts:
        out += [f"### Prompt {prompt}", "",
                "| Service | Run 1 | Run 2 | Run 3 | Average | API errors | Latency median / p90 (s) | Tokens in / out per call | Cost per 1k calls (USD) |",
                "|---|---|---|---|---|---|---|---|---|"]
        for s in services:
            rows = load(prompt, s)
            if not rows:
                continue
            runs = sorted({r["run"] for r in rows})
            per_run = [_acc([r for r in rows if r["run"] == n]) for n in runs]
            per_run += ["–"] * (3 - len(per_run))
            llm = [r for r in rows if r.get("llm_called") and not r["api_error"]
                   and r.get("latency_s") is not None]
            lat = [r["latency_s"] for r in llm]
            tin = statistics.mean(r["prompt_tokens"] or 0 for r in llm)
            tout = statistics.mean(r["completion_tokens"] or 0 for r in llm)
            n_err = sum(1 for r in rows if r["api_error"])
            out.append(f"| {s} | " + " | ".join(per_run) + f" | **{_acc(rows)}** | {n_err} | "
                       f"{statistics.median(lat):.2f} / {_quantile(lat, 0.9):.2f} | "
                       f"{tin:.0f} / {tout:.0f} | {1000 * call_cost(s, tin, tout):.3f} |")
        out.append("")
        cats = list(dict.fromkeys(c[1] for c in CASES))
        out += ["| Service | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
        for s in services:
            rows = load(prompt, s)
            if rows:
                out.append(f"| {s} | " + " | ".join(
                    _acc([r for r in rows if r["category"] == c]).split(" ")[0] for c in cats) + " |")
        out += ["", f"Failures ({prompt}):", "",
                "| Service | Run | Case | Utterance | Got | Why |", "|---|---|---|---|---|---|"]
        for s in services:
            for r in load(prompt, s):
                if r["ok"] is False:
                    out.append(f"| {s} | {r['run']} | {r['id']} | {r['text']} | `{_got(r)}` | {r['why']} |")
        out.append("")

    for old, new in zip(prompts, prompts[1:]):
        out += [f"### Items that flipped between {old} and {new} (passes / runs)", "",
                f"| Service | Case | Utterance | {old} | {new} |", "|---|---|---|---|---|"]
        for s in services:
            a, b = load(old, s), load(new, s)
            if not a or not b:
                continue
            na, nb = len({r["run"] for r in a}), len({r["run"] for r in b})
            for cid, _, _, text, _ in CASES:
                if not any(r["id"] == cid for r in a) or not any(r["id"] == cid for r in b):
                    continue   # case not run under both prompts
                pa = sum(1 for r in a if r["id"] == cid and r["ok"])
                pb = sum(1 for r in b if r["id"] == cid and r["ok"])
                if pa / na != pb / nb:
                    out.append(f"| {s} | {cid} | {text} | {pa}/{na} | {pb}/{nb} |")
        out.append("")

    out += ["### Logged spend this evaluation (scored calls + follow-up setup turns)", ""]
    for s in services:
        for prompt in prompts:
            rows = load(prompt, s)
            if rows and "cost_usd" in rows[0]:
                usd = sum(r.get("cost_usd", 0) + r.get("setup_cost_usd", 0) for r in rows)
                out.append(f"- {s} {prompt}: ${usd:.4f}")
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
    ap.add_argument("--ping", nargs="*", metavar="SERVICE",
                    help="connectivity check (default: all three services)")
    ap.add_argument("--services", nargs="+", default=[])
    ap.add_argument("--prompt", nargs="+", choices=sorted(PROMPTS), default=["v4"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--cases", nargs="+", default=[], help="only these case ids")
    ap.add_argument("--budget", type=float, default=None,
                    help="stop if any one service's estimated spend in this process exceeds USD")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.ping is not None:
        sys.exit(0 if ping(args.ping or PING_SERVICES) else 1)
    spend = _Spend(args.budget)
    try:
        for prompt in args.prompt:
            for s in args.services:
                n = run_service(s, prompt, args.runs, set(args.cases), spend)
                print(f"\n{s} {prompt}: {n}/{args.runs} complete runs")
    finally:
        for s, usd in spend.usd.items():
            print(f"TOTAL estimated spend {s}: ${usd:.4f} over {spend.calls[s]} calls")
    if args.report or args.services:
        services = [s for s in llm_parser.SERVICES
                    if any((RESULTS_DIR / p / f"{s}.jsonl").is_file() for p in PROMPTS)]
        md = report(services)
        (RESULTS_DIR / "summary.md").write_text(md + "\n")
        print("\n" + md)


if __name__ == "__main__":
    main()
