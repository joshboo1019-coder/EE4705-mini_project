"""
eval/noise_report.py — STUDENT B OWNS THIS FILE. Tables for eval/noise_fix.md
from the logged runs (no API calls).

    env -u PYTHONPATH .venv/bin/python eval/noise_report.py

Reads eval/results/noise/<prompt>/, eval/results/<prompt>/ (Standard) and
eval/results/hard/<prompt>/ for prompts v5 and v5.1. A "run" of a held-out
set is one (session, run) pair, since extra runs were made by a second
invocation.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval import task3_eval as t3  # noqa: E402
from eval import hard_cases as hc  # noqa: E402
from eval import noise_cases as nc  # noqa: E402

RES = Path(__file__).resolve().parent / "results"
SERVICES = ["qwen-flash", "gpt-5-nano"]
PROMPTS = ["v5", "v5.1"]
MOTION = {"move", "move_distance", "turn", "goto_object", "repeat", "until_see", "undo", "return_home"}


def rows(sub, prompt, service):
    path = RES / sub / prompt / f"{service}.jsonl"
    return [json.loads(line) for line in path.open()] if path.is_file() else []


def runs(rs):
    """[(session, run) -> rows] in log order."""
    out = {}
    for r in rs:
        out.setdefault((r["session"], r["run"]), []).append(r)
    return list(out.values())


def k(rs, cat=None):
    rs = [r for r in rs if (cat is None or r["category"] == cat) and r["ok"] is not None]
    return sum(bool(r["ok"]) for r in rs), len(rs)


def executed(r):
    """Accepted with at least one motion action."""
    acts = r["actions"].get("actions", []) if r["accepted"] else []
    return any(a.get("action") in MOTION for a in acts)


def noise_tables():
    out = ["### Set N (held out for v5.1), per category", "",
           "| Service | Prompt | noise (14) run 1 | runs 2, 3 | noise, 3 runs | foreign (5), 3 runs | "
           "codeswitch (5), 3 runs | must-reject (10) run 1 | runs 2, 3 | must-reject, 3 runs | "
           "all (24), 3 runs |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    for s in SERVICES:
        for p in PROMPTS:
            rr = runs(rows("noise", p, s))
            if not rr:
                continue
            allr = [r for run in rr for r in run]
            rej = [[r for r in run if r["category"] != "noise"] for run in rr]
            n1, n_rest = k(rr[0], "noise"), [k(run, "noise") for run in rr[1:]]
            j1, j_rest = k(rej[0]), [k(run) for run in rej[1:]]
            out.append(
                f"| {s} | {p} | {n1[0]}/{n1[1]} | {', '.join(f'{a}/{b}' for a, b in n_rest)} | "
                f"**{'%d/%d' % k(allr, 'noise')}** | {'%d/%d' % k(allr, 'foreign')} | "
                f"{'%d/%d' % k(allr, 'codeswitch')} | {j1[0]}/{j1[1]} | "
                f"{', '.join(f'{a}/{b}' for a, b in j_rest)} | "
                f"**{'%d/%d' % k([r for x in rej for r in x])}** | {'%d/%d' % k(allr)} |")
            noise_nonen = sum(1 for r in allr if r["category"] == "noise" and not r["accepted"]
                              and "english" in str(r["reject_reason"]).lower())
            noise_wrong = sum(1 for r in allr if r["category"] == "noise" and r["accepted"] and not r["ok"])
            rej_exec = sum(1 for r in allr if r["category"] != "noise" and executed(r))
            unsafe = sum(1 for r in allr if r.get("accepted_unsafe"))
            detail.append(f"| {s} | {p} | {len(rr)} | {noise_nonen} | {noise_wrong} | {rej_exec} | {unsafe} |")
    out += ["", "| Service | Prompt | runs | noise rejected as non-English | noise executed WRONGLY | "
            "must-reject EXECUTED | unsafe passed validator |", "|---|---|---|---|---|---|---|"] + detail
    # per case
    ids = [c[0] for c in nc.NOISE_CASES]
    texts = {c[0]: c[3] for c in nc.NOISE_CASES}
    hdr = [f"{s.split('-')[0]} {p}" for s in SERVICES for p in PROMPTS]
    out += ["", "Per case (passes / 3 runs):", "",
            "| Case | Utterance | " + " | ".join(hdr) + " |", "|---|---|" + "---|" * len(hdr)]
    for cid in ids:
        cells = []
        for s in SERVICES:
            for p in PROMPTS:
                rs = [r for r in rows("noise", p, s) if r["id"] == cid]
                cells.append(f"{sum(bool(r['ok']) for r in rs)}/{len(rs)}")
        out.append(f"| {cid} | {texts[cid]} | " + " | ".join(cells) + " |")
    return out


def standard_tables():
    cats = list(dict.fromkeys(c[1] for c in t3.CASES))
    out = ["### Standard set (45 cases, 1 run)", "",
           "| Service | Prompt | all | " + " | ".join(cats) + " |", "|---|---|---|" + "---|" * len(cats)]
    flips = []
    for s in SERVICES:
        for p in PROMPTS:
            rs = t3.load(p, s)
            if rs:
                out.append(f"| {s} | {p} | **{'%d/%d' % k(rs)}** | " +
                           " | ".join("%d/%d" % k(rs, c) for c in cats) + " |")
        a = {r["id"]: r for r in t3.load("v5", s)}
        b = {r["id"]: r for r in t3.load("v5.1", s)}
        for cid in a:
            if cid in b and bool(a[cid]["ok"]) != bool(b[cid]["ok"]):
                flips.append(f"| {s} | {cid} | {a[cid]['text']} | {'pass' if a[cid]['ok'] else 'FAIL'} | "
                             f"{'pass' if b[cid]['ok'] else 'FAIL: ' + b[cid]['why']} |")
    out += ["", "Flips v5 -> v5.1:", "", "| Service | Case | Utterance | v5 | v5.1 |",
            "|---|---|---|---|---|"] + flips
    return out


def hard_tables():
    cats = hc.CATEGORIES
    seen = {"noise", "codeswitch"}
    out = ["### Hard set (71 cases, 1 run; noise and codeswitch are SEEN, not held out for v5.1)", "",
           "| Service | Prompt | all | " + " | ".join(c + (" (seen)" if c in seen else "") for c in cats)
           + " | injection fooled | unsafe passed (all 71) |",
           "|---|---|---|" + "---|" * len(cats) + "---|---|"]
    for s in SERVICES:
        for p in PROMPTS:
            rr = runs(rows("hard", p, s))
            if not rr:
                continue
            rs = rr[-1]          # the latest run of that prompt
            fooled = sum(1 for r in rs if r["category"] == "injection" and r.get("raw_unsafe"))
            unsafe = sum(1 for r in rs if r.get("accepted_unsafe"))
            out.append(f"| {s} | {p} | **{'%d/%d' % k(rs)}** | " +
                       " | ".join("%d/%d" % k(rs, c) for c in cats) + f" | {fooled}/9 | **{unsafe}** |")
    out += ["", "Hard noise / codeswitch per case (v5 -> v5.1):", "",
            "| Service | Case | Utterance | v5 | v5.1 |", "|---|---|---|---|---|"]
    for s in SERVICES:
        a = {r["id"]: r for r in runs(rows("hard", "v5", s))[-1]}
        b = {r["id"]: r for r in runs(rows("hard", "v5.1", s))[-1]}
        for cid, cat, _, text, _ in hc.HARD_CASES:
            if cat in seen and bool(a[cid]["ok"]) != bool(b[cid]["ok"]):
                out.append(f"| {s} | {cid} | {text} | {'pass' if a[cid]['ok'] else 'FAIL'} | "
                           f"{'pass' if b[cid]['ok'] else 'FAIL: ' + b[cid]['why']} |")
    return out


def spend():
    out = ["### Spend (this task)", "", "| Log | calls | USD |", "|---|---|---|"]
    total = 0.0
    for sub in ["noise/v5", "noise/v5.1", "v5.1", "hard/v5.1"]:
        for s in SERVICES:
            path = RES / sub / f"{s}.jsonl"
            if not path.is_file():
                continue
            rs = [json.loads(line) for line in path.open()]
            usd = sum(r.get("cost_usd", 0.0) + r.get("setup_cost_usd", 0.0) for r in rs)
            total += usd
            out.append(f"| `eval/results/{sub}/{s}.jsonl` | {len(rs)} | ${usd:.4f} |")
    out.append(f"| **total** | | **${total:.4f}** |")
    return out


if __name__ == "__main__":
    print("\n".join(noise_tables() + [""] + standard_tables() + [""] + hard_tables() + [""] + spend()))
