"""
eval/upgrade_report.py — STUDENT B OWNS THIS FILE. Tables and figures for
eval/upgrade_eval.md from the logged runs (no API calls).

    env -u PYTHONPATH .venv/bin/python eval/upgrade_report.py   # prints markdown, writes PNGs

Reads eval/results/v4|v5/<service>.jsonl (Standard set) and
eval/results/hard/<prompt>/<service>.jsonl (Hard set); figures go to
eval/results/hard/*.png.
"""

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval import task3_eval as t3  # noqa: E402
from eval import hard_cases as hc  # noqa: E402

RES = Path(__file__).resolve().parent / "results"
SERVICES = ["qwen-flash", "gpt-5-nano", "gemini-3.8-flash"]
STD_CATS = list(dict.fromkeys(c[1] for c in t3.CASES))


def _pct(rows):
    scored = [r for r in rows if r["ok"] is not None]
    if not scored:
        return "–"
    k = sum(bool(r["ok"]) for r in scored)
    return f"{100 * k / len(scored):.0f}% ({k}/{len(scored)})"


def _short(rows):
    scored = [r for r in rows if r["ok"] is not None]
    if not scored:
        return "–"
    k = sum(bool(r["ok"]) for r in scored)
    return f"{k}/{len(scored)}"


RESCORE = False   # True: re-validate the logged raw replies with the current validator


def _rescore(r):
    """Same raw reply, current validator and oracles (no LLM call)."""
    import contextlib
    import io
    from dialogue import llm_parser
    if not r.get("llm_called") or r.get("api_error") or r.get("raw") is None:
        return r
    check = {c[0]: c[4] for c in hc.HARD_CASES}[r["id"]]
    with contextlib.redirect_stdout(io.StringIO()):
        res = llm_parser._validate(r["raw"])
    ok, why = check(res)
    return dict(r, ok=ok, why=why, accepted=res.accepted, reject_reason=res.reject_reason,
                suggestion=getattr(res, "suggestion", None),
                actions=json.loads(llm_parser.history_entry(res)),
                raw_unsafe=hc.raw_unsafe(r["raw"]), accepted_unsafe=hc.accepted_unsafe(res),
                rescored=True)


def load_hard(prompt, service, tag=None, rescore=None):
    path = RES / "hard" / (tag or prompt) / f"{service}.jsonl"
    if not path.is_file():
        return []
    latest = {}
    for line in path.open():
        r = json.loads(line)
        latest[(r["run"], r["id"])] = r
    rows = sorted(latest.values(), key=lambda r: (r["run"], r["id"]))
    if RESCORE if rescore is None else rescore:
        rows = [_rescore(r) for r in rows]
    return rows


def rescore_flips(have):
    out = ["| Run | Case | as run | re-scored | re-scored result |", "|---|---|---|---|---|"]
    for p, s, tag in have:
        a = {r["id"]: r for r in load_hard(p, s, tag, rescore=False)}
        for r in load_hard(p, s, tag, rescore=True):
            o = a[r["id"]]
            if bool(o["ok"]) != bool(r["ok"]) or bool(o.get("raw_unsafe")) != bool(r.get("raw_unsafe")):
                out.append(f"| {s} {p} | {r['id']} | {'pass' if o['ok'] else 'FAIL'}"
                           f"{' (fooled)' if o.get('raw_unsafe') else ''} | "
                           f"{'pass' if r['ok'] else 'FAIL'}{' (fooled)' if r.get('raw_unsafe') else ''} | "
                           f"{r['why'] or t3._got(r)} |")
    return "\n".join(out)


def _lat(rows):
    lat = [r["latency_s"] for r in rows if r.get("llm_called") and r.get("latency_s") and not r["api_error"]]
    tin = [r["prompt_tokens"] for r in rows if r.get("prompt_tokens")]
    return (f"{statistics.median(lat):.2f} / {t3._quantile(lat, 0.9):.2f}" if lat else "–",
            f"{statistics.mean(tin):.0f}" if tin else "–")


def standard_tables():
    out = ["| Service | v4 (45 cases) | v5 (45 cases) | API errors v5 | Latency median / p90 v4 → v5 (s) | Tokens in v4 → v5 |",
           "|---|---|---|---|---|---|"]
    for s in SERVICES:
        a, b = t3.load("v4", s), t3.load("v5", s)
        if not b:
            continue
        la, ta = _lat(a)
        lb, tb = _lat(b)
        out.append(f"| {s} | {_pct(a)} | **{_pct(b)}** | {sum(1 for r in b if r['api_error'])} | "
                   f"{la} → {lb} | {ta} → {tb} |")
    out += ["", "| Service | Prompt | " + " | ".join(STD_CATS) + " |", "|---|---|" + "---|" * len(STD_CATS)]
    for s in SERVICES:
        for p in ("v4", "v5"):
            rows = t3.load(p, s)
            if rows:
                out.append(f"| {s} | {p} | " + " | ".join(
                    _short([r for r in rows if r["category"] == c]) for c in STD_CATS) + " |")
    out += ["", "Flips v4 → v5 (1 run each):", "", "| Service | Case | Utterance | v4 | v5 | v5 output |",
            "|---|---|---|---|---|---|"]
    for s in SERVICES:
        a = {r["id"]: r for r in t3.load("v4", s)}
        for r in t3.load("v5", s):
            o = a.get(r["id"])
            if o is not None and bool(o["ok"]) != bool(r["ok"]):
                out.append(f"| {s} | {r['id']} | {r['text']} | {'pass' if o['ok'] else 'FAIL'} | "
                           f"{'pass' if r['ok'] else 'FAIL'} | `{t3._got(r)}` |")
    return "\n".join(out)


def hard_tables():
    cols = [("v5", s, None) for s in SERVICES] + [("v4", "qwen-flash", None)]
    have = [(p, s, tag) for p, s, tag in cols if load_hard(p, s, tag)]
    out = ["| Category | n | " + " | ".join(f"{s} {p}" for p, s, _ in have) + " |",
           "|---|---|" + "---|" * len(have)]
    for cat in hc.CATEGORIES:
        n = sum(1 for c in hc.HARD_CASES if c[1] == cat)
        out.append(f"| {cat} | {n} | " + " | ".join(
            _short([r for r in load_hard(p, s, tag) if r["category"] == cat]) for p, s, tag in have) + " |")
    out.append(f"| **all** | {len(hc.HARD_CASES)} | " + " | ".join(
        f"**{_pct(load_hard(p, s, tag))}**" for p, s, tag in have) + " |")
    lat = [_lat(load_hard(p, s, tag)) for p, s, tag in have]
    out.append("| latency median / p90 (s) | | " + " | ".join(l[0] for l in lat) + " |")
    out.append("| tokens in (mean) | | " + " | ".join(l[1] for l in lat) + " |")
    return "\n".join(out), have


def injection_table(have):
    out = ["| Run | injection cases safe (pass) | LLM fooled (raw reply unsafe) | unsafe command passed the validator | "
           "fooled on any Hard case | unsafe passed on any Hard case |", "|---|---|---|---|---|---|"]
    for p, s, tag in have:
        rows = load_hard(p, s, tag)
        inj = [r for r in rows if r["category"] == "injection"]
        f_inj = [r["id"] for r in inj if r.get("raw_unsafe")]
        u_inj = [r["id"] for r in inj if r.get("accepted_unsafe")]
        f_all = [r["id"] for r in rows if r.get("raw_unsafe")]
        u_all = [r["id"] for r in rows if r.get("accepted_unsafe")]
        out.append(f"| {s} {p} | {_short(inj)} | {len(f_inj)}/{len(inj)} {' '.join(f_inj)} | "
                   f"**{len(u_inj)}**/{len(inj)} | {len(f_all)}/{len(rows)} {' '.join(f_all)} | "
                   f"**{len(u_all)}**/{len(rows)} |")
    return "\n".join(out)


def detail_table(have, cats):
    out = ["| Run | Case | Utterance | Result | Why / got | raw_unsafe |", "|---|---|---|---|---|---|"]
    for p, s, tag in have:
        for r in load_hard(p, s, tag):
            if r["category"] not in cats:
                continue
            got = t3._got(r)
            if r.get("suggestion"):
                got += f' (suggestion: "{r["suggestion"]}")'
            out.append(f"| {s} {p} | {r['id']} | {r['text'][:70]} | {'pass' if r['ok'] else 'FAIL'} | "
                       f"{(r['why'] + ' — ') if r['why'] else ''}`{got[:160]}` | {r.get('raw_unsafe') or ''} |")
    return "\n".join(out)


def failures(have):
    out = ["| Run | Case | Category | Utterance | Why |", "|---|---|---|---|---|"]
    for p, s, tag in have:
        for r in load_hard(p, s, tag):
            if r["ok"] is False:
                out.append(f"| {s} {p} | {r['id']} | {r['category']} | {r['text'][:60]} | {r['why'][:110]} |")
    return "\n".join(out)


def figure(have, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {("v5", "qwen-flash"): "#2a78d6", ("v5", "gpt-5-nano"): "#eb6834",
              ("v5", "gemini-3.8-flash"): "#1baf7a", ("v4", "qwen-flash"): "#a3a29c"}
    cats = hc.CATEGORIES
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=150)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    k = len(have)
    width = 0.8 / k
    for j, (p, s, tag) in enumerate(have):
        rows = load_hard(p, s, tag)
        vals = []
        for c in cats:
            rc = [r for r in rows if r["category"] == c and r["ok"] is not None]
            vals.append(100 * sum(bool(r["ok"]) for r in rc) / len(rc) if rc else 0)
        xs = [i + (j - (k - 1) / 2) * width for i in range(len(cats))]
        ax.bar(xs, vals, width=width - 0.02, color=colors.get((p, s), "#888"),
               label=f"{s} ({p})", edgecolor="#fcfcfb", linewidth=1)
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels(cats, color="#52514e", fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_ylabel("accuracy (%)", color="#52514e", fontsize=9)
    ax.tick_params(axis="y", colors="#52514e", labelsize=8)
    ax.grid(axis="y", color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c9c8c2")
    ax.set_title("Hard set (held out, 1 run): accuracy per category", color="#0b0b0b", fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=8, ncol=k, loc="upper left", bbox_to_anchor=(0, -0.1))
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    global RESCORE
    if "--rescore" in sys.argv:
        RESCORE = True
    print("## Standard set\n")
    print(standard_tables())
    table, have = hard_tables()
    print("\n## Hard set\n")
    print(table)
    print("\n## Injection\n")
    print(injection_table(have))
    print("\n## Code-switching and out-of-range details\n")
    print(detail_table(have, {"codeswitch", "numbers", "injection"}))
    print("\n## Hard-set failures\n")
    print(failures(have))
    print("\n## Re-scored with the fixed validator (as run -> re-scored)\n")
    print(rescore_flips(have))
    figure(have, RES / "hard" / "hard_by_category.png")
    total, per = t3.spend_total()
    print(f"\nSpend: ${total:.4f}")
    for k, v in sorted(per.items()):
        print(f"  {k}: ${v:.4f}")


if __name__ == "__main__":
    main()
