# Owner: Student B (report assets; all groups' data)
"""
docs/report_assets/final/make_assets.py — regenerate every report figure from the logs.

Run from the repo root (no sim, no API calls):

    env -u PYTHONPATH .venv/bin/python docs/report_assets/final/make_assets.py \
        [--results-root DIR ...] [--s3-runs RUN_OR_DIR ...] [--v6] [--v6-root DIR] [--out DIR]

Outputs (PNG at 300 dpi + CSV each, plus CAPTIONS.md) in docs/report_assets/final/:

  1. s3_success_ci        S3 per-scenario strict success, Wilson 95 % CI over --s3-runs
  2. s3_history           strict S3 success per run, chronological, coloured by era
  3. parser_v5_v6         parser accuracy per category per model, Standard (45) + Hard (71)
  4. turn_accuracy_latency  Task 2 |settled error| before/after F3 + stop latency before/after
  5. contacts             S3 contact samples per scenario (target / other objects / terrain)
  6. parser_latency_cost  parser latency p50/p95 and USD per 100 commands (Standard set, v4 + v5)

Inputs:
  * e2e runs: <root>/<run>/results.jsonl (eval/e2e/run_all.py). A run is looked up by name in
    every --results-root (first hit wins), so runs from several checkouts can be combined.
    --s3-runs takes run names or paths. Default: every *fixfinal_s3_r* run with all 10 S3
    scenarios; if there is none, the n = 3 "final" set of eval/e2e/COMPARISON.md
    (0221_final, 0304_final_rep2, 0317_final_rep3).
  * parser: <parser-root>/<prompt>/<service>.jsonl and <parser-root>/hard/<prompt>/<service>.jsonl
    (eval/task3_eval.py); prices = eval/task3_eval.py PRICES (USD per 1M tokens, in/out).
    v6 is used when <v6-root>/v6 exists (always with --v6; it then fails loudly if missing).
  * Task 2: docs/report_assets/task2/logs/{turn_trials,f3_exec}_{left,right}.jsonl, f3_stop_latency.jsonl.
"""

import argparse
import ast
import csv
import json
import math
import re
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
OUT_DEFAULT = Path(__file__).resolve().parent

# Categorical slots (fixed order, never cycled) + neutral ink.
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "legend.frameon": False, "figure.dpi": 100, "savefig.dpi": 300,
    "savefig.bbox": "tight", "figure.facecolor": "white",
})

CAPTIONS = {}


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(REPO))
    except ValueError:
        return str(p)


# --------------------------------------------------------------------------- e2e runs

def load_run(d):
    recs = []
    f = Path(d) / "results.jsonl"
    for line in f.read_text().splitlines():
        if line.strip():
            recs.append(json.loads(line))
    return recs


def s3_records(d):
    """{scenario '01'..: record} for the S3 suite of a run (last record wins)."""
    return {r["scenario"]: r for r in load_run(d) if r.get("suite") == "S3"}


def all_runs(roots):
    """{run name: dir} over every results root (first root wins on a name clash)."""
    runs = {}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            print(f"[warn] results root not found: {root}", file=sys.stderr)
            continue
        for d in sorted(root.iterdir()):
            if (d / "results.jsonl").is_file() and d.name not in runs:
                runs[d.name] = d
    return runs


def resolve_run(name, runs):
    p = Path(name)
    if (p / "results.jsonl").is_file():
        return p.name, p
    for k, d in runs.items():
        if k == name or k.endswith(name):
            return k, d
    raise SystemExit(f"run not found in any --results-root: {name}")


def is_complete_s3(d):
    return len(s3_records(d)) >= 10


FALLBACK_S3 = ["20261004-0221_final", "20261004-0304_final_rep2", "20261004-0317_final_rep3"]


def pick_s3_runs(args, runs):
    if args.s3_runs:
        return [resolve_run(x, runs) for x in args.s3_runs], "given on the command line"
    ff = [(k, d) for k, d in runs.items() if "fixfinal_s3_r" in k]
    full = [(k, d) for k, d in ff if args.allow_partial or is_complete_s3(d)]
    skipped = [k for k, _ in ff if (k, runs[k]) not in full]
    if skipped:
        print(f"[info] skipping incomplete fixfinal runs (< 10 S3 records): {skipped}", file=sys.stderr)
    if full:
        return full, "fixfinal_s3_r* runs"
    return [resolve_run(x, runs) for x in FALLBACK_S3], "fallback: n = 3 final set of eval/e2e/COMPARISON.md"


def scen_label(rec):
    t = rec["meta"]["target"].replace("_", " ")
    if str(rec["meta"].get("expected", "")).startswith("FAIL"):
        t += " (absent)"
    return f"{rec['scenario']} {t}"


def fig_s3_success(args, runs, out):
    picked, why = pick_s3_runs(args, runs)
    data = {name: s3_records(d) for name, d in picked}
    scen = sorted({s for r in data.values() for s in r})
    rows, labels, ks, ns = [], [], [], []
    for s in scen:
        rs = [data[n][s] for n, _ in picked if s in data[n]]
        k = sum(bool((r.get("eval") or {}).get("pass")) for r in rs)
        n = len(rs)
        lo, hi = wilson(k, n)
        lab = scen_label(rs[0])
        tds = ";".join(str((r.get("eval") or {}).get("true_d")) for r in rs)
        rows.append([s, lab.split(" ", 1)[1], k, n, f"{k / n:.3f}", f"{lo:.3f}", f"{hi:.3f}", tds])
        labels.append(lab)
        ks.append(k)
        ns.append(n)
    K, N = sum(ks), sum(ns)
    lo, hi = wilson(K, N)
    rows.append(["all", "pooled over scenarios", K, N, f"{K / N:.3f}", f"{lo:.3f}", f"{hi:.3f}", ""])
    hdr = ["scenario", "target", "k_strict", "n_runs", "rate", "wilson95_lo", "wilson95_hi", "true_d_per_run"]
    write_csv(out / "s3_success_ci.csv", hdr, rows + [["#runs", " ".join(n for n, _ in picked), "", "", "", "", "", why]])
    print(f"\n# S3 strict success per scenario ({why}): {', '.join(n for n, _ in picked)}")
    print(f"{'scenario':<34}{'k/n':>7}  Wilson 95 % CI")
    for r in rows:
        print(f"{(r[0] + ' ' + r[1]):<34}{f'{r[2]}/{r[3]}':>7}  [{r[5]}, {r[6]}]")

    labels_all = labels + ["all scenarios (pooled)"]
    rate = [k / n for k, n in zip(ks, ns)] + [K / N]
    ci = [wilson(k, n) for k, n in zip(ks, ns)] + [(lo, hi)]
    y = np.arange(len(labels_all))[::-1].astype(float)
    y[-1] -= 0.4
    fig, ax = plt.subplots(figsize=(6.4, 0.32 * len(labels_all) + 1.2))
    for yi, r, (l, h), lab in zip(y, rate, ci, labels_all):
        col = INK if lab.startswith("all") else C1
        ax.plot([l, h], [yi, yi], color=col, lw=2, solid_capstyle="round", alpha=0.45)
        ax.plot([r], [yi], "o", ms=8, color=col, mec="white", mew=1.5, zorder=3)
    for yi, k, n in zip(y, ks + [K], ns + [N]):
        ax.text(1.04, yi, f"{k}/{n}", va="center", ha="left", color=INK2, fontsize=8, clip_on=False)
    ax.set_yticks(y, labels_all)
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("strict success rate (dot) with Wilson 95 % CI (line)")
    ax.grid(axis="y", visible=False)
    nrun = len(picked)
    ax.set_title(f"S3 Task 4 strict success per scenario (n = {nrun} run{'s' if nrun != 1 else ''} each)",
                 loc="left")
    fig.savefig(out / "s3_success_ci.png")
    plt.close(fig)
    CAPTIONS["s3_success_ci.png"] = (
        f"S3 (Task 4) strict success per scenario (true stop distance ≤ 0.80 m, no fall; scenario 10 = "
        f"correct not-found), dot = k/n, line = Wilson 95 % CI; n = {nrun} runs per scenario, {N} trials "
        f"pooled ({K}/{N}); runs: {', '.join(n for n, _ in picked)} ({why}); source "
        f"eval/e2e/results/<run>/results.jsonl.")
    return picked


# era of a run (S3 history); the first matching rule wins.
ERA_GT, ERA_NOGT, ERA_FINAL = ("GT height (sim xpos) + v4/v5", "no-GT height", "final (fix/final, tag final)")
ERA_R3 = "final-r3 (rc + tag)"
ERA_RULES = [
    ("rc_s3_r", ERA_R3, True, "rc: final-r2 + iter/close-range-c1 + v5.1 + fix/hygiene"),
    ("r3tag_s3_r", ERA_R3, True, "tag final-r3/r4 S3 repeat (n = 5 with the rc runs)"),
    ("p2a_", None, True, "excluded: iter/chair-safety gate (partial, not merged)"),
    ("p2b_", None, True, "excluded: iter/avoid runs (not merged)"),
    ("iter2_", None, True, "excluded: iter/stopsign-plate runs (not merged)"),
    ("video_task4", None, True, "excluded: video takes, 2 scenarios only"),
    ("fixfinal_s3_r", ERA_FINAL, True, "fix/final S3 repeat"),
    ("tag_s3_r", ERA_FINAL, True, "tag final S3 repeat (stats, n = 5 with the fixfinal runs)"),
    ("video_task4", None, True, "excluded: video takes, 2 scenarios only"),
    ("iter1_", None, True, "excluded: iter/close-range-c1, never merged"),
    ("f1gate", None, True, "excluded: F1 gate ran 2 scenarios only"),
    ("vt4_candidates", None, True, "excluded: video takes, 2 scenarios only"),
    ("stopsign_eval", None, True, "excluded: assist/stopsign, never merged (COMPARISON.md)"),
    ("0206_final", None, True, "excluded: superseded by 0221_final (S2 STATE regression re-run)"),
    ("no_gt_height", ERA_NOGT, True, "no-GT height estimate (assist/no-gt-height)"),
    ("premerge_gate", ERA_NOGT, True, "pre-final gate on release/merge (no-GT)"),
    ("baseline", ERA_GT, False, "merged main before the per-class stop margin"),
    ("p2a_task4_via_main", ERA_GT, False, "S3 via main.py --scenario, before the stop margin"),
    ("p2b_c2_margin_v2", ERA_GT, True, "per-class stop margin"),
    ("p2b_c2_margin", ERA_GT, True, "stop margin v1 (one margin for all classes)"),
    ("_final", ERA_GT, True, "b/overnight-all final"),
    ("morning_merge", ERA_GT, True, "morning merge"),
]


def classify(name):
    for pat, era, margin, note in ERA_RULES:
        if pat in name:
            return era, margin, note
    return None, None, "excluded: no era rule matches this run name"


def fig_s3_history(args, runs, out):
    rows, plot = [], []
    for name, d in sorted(runs.items()):
        s3 = s3_records(d)
        if not s3:
            continue
        era, margin, note = classify(name)
        k = sum(bool((r.get("eval") or {}).get("pass")) for r in s3.values())
        n = len(s3)
        if era and n < 10:
            if not args.allow_partial:
                era, note = None, f"excluded: incomplete ({n}/10 S3 scenarios)"
        rows.append([name, rel(d), n, k, f"{k / n:.2f}", era or "", "" if era is None else int(margin),
                     "yes" if era else "no", note])
        if era:
            plot.append((name, k, n, era, margin))
    write_csv(out / "s3_history.csv",
              ["run", "dir", "n_s3_scenarios", "k_strict", "fraction", "era", "stop_margin", "plotted", "note"], rows)

    era_col = {ERA_GT: C1, ERA_NOGT: C2, ERA_FINAL: C3, ERA_R3: "#7b4fa8"}
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    x = np.arange(len(plot))
    for xi, (name, k, n, era, margin) in zip(x, plot):
        ax.bar(xi, k / n, width=0.72, color=era_col[era] if margin else "white", edgecolor=era_col[era],
               lw=1.6, hatch=None if margin else "////")
        ax.text(xi, k / n + 0.015, f"{k}/{n}", ha="center", va="bottom", fontsize=7.5, color=INK2)
    ax.set_xticks(x, [re.sub(r"^\d{8}-", "", p[0]) for p in plot], rotation=55, ha="right", fontsize=7.5)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("strict success (fraction of S3 scenarios)")
    ax.grid(axis="x", visible=False)
    from matplotlib.patches import Patch
    hand = [Patch(facecolor=era_col[e], edgecolor=era_col[e], label=e) for e in era_col
            if any(p[3] == e for p in plot)]
    hand.append(Patch(facecolor="white", edgecolor=INK2, hatch="////", label="before the per-class stop margin"))
    ax.legend(handles=hand, loc="upper left", fontsize=7.5, ncol=2)
    ax.set_title("S3 strict success per run, chronological (run dir prefix = HHMM on 2026-10-04)", loc="left")
    fig.savefig(out / "s3_history.png")
    plt.close(fig)
    eras = {e: sum(1 for p in plot if p[3] == e) for e in era_col}
    missing = [] if eras[ERA_FINAL] else ["no complete fixfinal_s3_r* run yet"]
    CAPTIONS["s3_history.png"] = (
        f"S3 strict success per run (k/10 scenarios, one trial each) in chronological order, coloured by era "
        f"({'; '.join(f'{e}: {c} runs' for e, c in eras.items())}); hatched = before the per-class stop "
        f"margin; {len(plot)} runs plotted"
        + (f" ({'; '.join(missing)})" if missing else "")
        + "; run-to-era mapping and exclusions in s3_history.csv; source eval/e2e/results/<run>/results.jsonl.")


def fig_contacts(args, runs, picked, out):
    """Per-scenario contact samples by class; falls back to the old any-contact field."""
    def with_cc(names):
        return [(n, runs.get(n) or d) for n, d in names
                if any((r.get("eval") or {}).get("contact_classes") for r in s3_records(d).values())]

    src = with_cc(picked)
    how = "the S3 runs of figure 1"
    if not src:
        cand = [(k, d) for k, d in runs.items() if ("fixfinal" not in k or args.allow_partial or is_complete_s3(d))]
        src = with_cc(cand)
        how = "every run that logs contact_classes"
    rows = []
    if src:
        agg = {}
        for name, d in src:
            for s, r in s3_records(d).items():
                cc = (r.get("eval") or {}).get("contact_classes")
                if not cc:
                    continue
                a = agg.setdefault(s, {"label": scen_label(r), "n": 0, "any": 0, "target": [], "objects": [],
                                       "terrain": [], "hit": set()})
                a["n"] += 1
                a["any"] += int(bool(cc.get("target") or cc.get("objects") or cc.get("terrain")))
                for c in ("target", "objects", "terrain"):
                    a[c].append(int(cc.get(c) or 0))
                a["hit"].update(cc.get("objects_hit") or [])
                rows.append([s, name, cc.get("target"), cc.get("objects"), cc.get("terrain"),
                             " ".join(cc.get("objects_hit") or [])])
        write_csv(out / "contacts.csv", ["scenario", "run", "target_samples", "other_object_samples",
                                         "terrain_samples", "objects_hit"], rows)
        scen = sorted(agg)
        fig, ax = plt.subplots(figsize=(6.4, 0.34 * len(scen) + 1.3))
        y = np.arange(len(scen))[::-1]
        left = np.zeros(len(scen))
        for c, col, lab in (("target", C1, "target object"), ("objects", C2, "other objects"),
                            ("terrain", C3, "terrain")):
            v = np.array([statistics.mean(agg[s][c]) for s in scen])
            ax.barh(y, v, left=left, color=col, height=0.62, edgecolor="white", lw=1, label=lab)
            left += v
        for yi, s, tot in zip(y, scen, left):
            ax.text(tot + max(left.max(), 1) * 0.01, yi, f"{agg[s]['any']}/{agg[s]['n']} runs with contact",
                    va="center", fontsize=7.5, color=INK2)
        ax.set_yticks(y, [agg[s]["label"] for s in scen])
        ax.set_xlim(0, max(left.max(), 1) * 1.35)
        ax.set_xlabel("contact samples per run (mean over runs; sim trace)")
        ax.grid(axis="y", visible=False)
        ax.legend(loc="lower right", fontsize=7.5)
        ax.set_title("S3 robot contacts per scenario, by what was touched", loc="left")
        fig.savefig(out / "contacts.png")
        plt.close(fig)
        nruns = len(src)
        CAPTIONS["contacts.png"] = (
            f"S3 robot contact samples per scenario split into target object / other objects / terrain "
            f"(mean per run; label = runs with any contact / runs), from eval.contact_classes of {how}: "
            f"{nruns} runs ({', '.join(n for n, _ in src)}), {len(rows)} scenario trials; source "
            f"eval/e2e/results/<run>/results.jsonl.")
        return
    # fallback: the older 'contacts' field (unique body|geom pairs, any contact)
    agg = {}
    for name, d in picked:
        for s, r in s3_records(d).items():
            a = agg.setdefault(s, {"label": scen_label(r), "n": 0, "any": 0})
            a["n"] += 1
            a["any"] += int(bool((r.get("eval") or {}).get("contacts")))
            rows.append([s, name, len((r.get("eval") or {}).get("contacts") or [])])
    write_csv(out / "contacts.csv", ["scenario", "run", "contact_pairs_any"], rows)
    scen = sorted(agg)
    fig, ax = plt.subplots(figsize=(6.4, 0.34 * len(scen) + 1.3))
    y = np.arange(len(scen))[::-1]
    ax.barh(y, [agg[s]["any"] / agg[s]["n"] for s in scen], color=C1, height=0.62)
    ax.set_yticks(y, [agg[s]["label"] for s in scen])
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("fraction of runs with any robot contact")
    fig.savefig(out / "contacts.png")
    plt.close(fig)
    CAPTIONS["contacts.png"] = (
        f"No run logs contact_classes yet: fraction of runs with any robot contact (older eval.contacts "
        f"field, no target/object/terrain split) per S3 scenario over {len(picked)} runs; source "
        f"eval/e2e/results/<run>/results.jsonl.")


# --------------------------------------------------------------------------- parser

def load_jsonl(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]


def services_in(d):
    return sorted(p.stem for p in Path(d).glob("*.jsonl")) if Path(d).is_dir() else []


MODEL_ORDER = ["qwen-flash", "gpt-5-nano", "gemini-3.8-flash"]


def fig_parser(args, out):
    root = Path(args.parser_root)
    v6root = Path(args.v6_root or args.parser_root)
    sets = [("Standard", root / "v5", v6root / "v6"), ("Hard", root / "hard" / "v5", v6root / "hard" / "v6")]
    have_v6 = (v6root / "v6").is_dir() or (v6root / "hard" / "v6").is_dir()
    if args.v6 and not have_v6:
        raise SystemExit(f"--v6 given but no v6 results under {v6root}")
    if args.no_v6:
        have_v6 = False
    models = [m for m in MODEL_ORDER if any(m in services_in(s[1]) for s in sets)]
    models += sorted({m for s in sets for m in services_in(s[1])} - set(models))
    rows, acc = [], {}
    for set_name, d5, d6 in sets:
        for ver, d in (("v5", d5), ("v6", d6)):
            if ver == "v6" and not have_v6:
                continue
            for m in services_in(d):
                recs = [r for r in load_jsonl(Path(d) / f"{m}.jsonl") if r.get("api_error") is None]
                cats = list(dict.fromkeys(r["category"] for r in recs))
                for c in cats + ["ALL"]:
                    rs = recs if c == "ALL" else [r for r in recs if r["category"] == c]
                    k, n = sum(bool(r["ok"]) for r in rs), len(rs)
                    acc[(set_name, ver, m, c)] = (k, n)
                    rows.append([set_name, ver, m, c, k, n, f"{k / n:.3f}" if n else "", rel(Path(d) / f"{m}.jsonl")])
    write_csv(out / "parser_v5_v6.csv",
              ["set", "prompt", "model", "category", "k_ok", "n", "accuracy", "source"], rows)

    vers = ["v5", "v6"] if have_v6 else ["v5"]
    vcol = {"v5": C1, "v6": C2}
    fig, axes = plt.subplots(2, len(models), figsize=(2.6 * len(models) + 1.6, 7.2), sharex=True,
                             gridspec_kw={"height_ratios": [10, 10]})
    axes = np.atleast_2d(axes)
    for i, (set_name, _, _) in enumerate(sets):
        cats = []
        for (s, v, m, c) in acc:
            if s == set_name and c not in cats and c != "ALL":
                cats.append(c)
        cats = ["ALL"] + cats
        for j, m in enumerate(models):
            ax = axes[i, j]
            y = np.arange(len(cats))[::-1].astype(float)
            h = 0.8 / len(vers)
            for vi, v in enumerate(vers):
                vals, labs = [], []
                for c in cats:
                    k, n = acc.get((set_name, v, m, c), (0, 0))
                    vals.append(k / n if n else np.nan)
                    labs.append(f"{k}/{n}" if n else "n/a")
                off = (vi - (len(vers) - 1) / 2) * h
                ax.barh(y - off, np.nan_to_num(vals), height=h * 0.92, color=vcol[v], label=f"prompt {v}")
                for yi, val, lab in zip(y - off, vals, labs):
                    ax.text((0 if np.isnan(val) else val) + 0.02, yi, lab, va="center", fontsize=6.3, color=INK2)
            ax.set_xlim(0, 1.32)
            ax.set_xticks([0, 0.5, 1.0])
            ax.grid(axis="y", visible=False)
            if j == 0:
                ax.set_yticks(y, [("overall" if c == "ALL" else c) for c in cats])
            else:
                ax.set_yticks(y, [""] * len(cats))
            n_set = acc.get((set_name, "v5", m, "ALL"), (0, 0))[1]
            ax.set_title(f"{m}\n{set_name} set (n = {n_set})", fontsize=8.5)
            ax.axhline(y[0] - 0.55, color=GRID, lw=0.8)
            if i == 1:
                ax.set_xlabel("accuracy (fraction ok)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=len(vers), fontsize=8)
    fig.suptitle("Command-parser accuracy per category" + ("" if have_v6 else " (prompt v5; v6 not available)"),
                 x=0.01, ha="left", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out / "parser_v5_v6.png")
    plt.close(fig)
    v6_models = sorted({m for (s, v, m, c) in acc if v == "v6"})
    CAPTIONS["parser_v5_v6.png"] = (
        "LLM command-parser accuracy per category and model on the Standard set (45 commands) and the "
        "held-out Hard set (71), one run each, bar label = ok/n"
        + (f"; prompt v5 vs v6 (v6 for {', '.join(v6_models)} only)" if have_v6 else
           "; prompt v5 only (v6 results not yet in eval/results/v6)")
        + f"; source {rel(root)}/{{v5,hard/v5}}"
        + (f" and {rel(v6root)}/{{v6,hard/v6}}" if have_v6 else "") + "/<model>.jsonl (eval/task3_eval.py).")


def load_prices():
    src = (REPO / "eval" / "task3_eval.py").read_text()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "PRICES" for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit("PRICES not found in eval/task3_eval.py")


def fig_latency_cost(args, out):
    prices = load_prices()
    root = Path(args.parser_root)
    vers = [v for v in ("v4", "v5") if (root / v).is_dir()]
    models = [m for m in MODEL_ORDER if any((root / v / f"{m}.jsonl").is_file() for v in vers)]
    rows, res = [], {}
    for v in vers:
        for m in models:
            p = root / v / f"{m}.jsonl"
            if not p.is_file():
                continue
            recs = [r for r in load_jsonl(p) if r.get("api_error") is None]
            lat = [r["latency_s"] for r in recs if r.get("llm_called") and r.get("latency_s") is not None]
            pin, pout = prices.get(m, (0.0, 0.0))
            cost = [((r.get("prompt_tokens") or 0) * pin + (r.get("completion_tokens") or 0) * pout) / 1e6
                    for r in recs]
            p50, p95 = np.percentile(lat, 50), np.percentile(lat, 95)
            c100 = 100 * statistics.mean(cost)
            tin = statistics.mean([r.get("prompt_tokens") or 0 for r in recs if r.get("llm_called")])
            tout = statistics.mean([r.get("completion_tokens") or 0 for r in recs if r.get("llm_called")])
            res[(v, m)] = (p50, p95, c100, len(lat), len(recs))
            rows.append([v, m, len(recs), len(lat), f"{p50:.3f}", f"{p95:.3f}", f"{c100:.5f}", f"{tin:.0f}",
                         f"{tout:.1f}", pin, pout, rel(p)])
    write_csv(out / "parser_latency_cost.csv",
              ["prompt", "model", "n_commands", "n_llm_calls", "latency_p50_s", "latency_p95_s",
               "usd_per_100_commands", "mean_prompt_tokens", "mean_completion_tokens", "usd_per_1M_in",
               "usd_per_1M_out", "source"], rows)
    vcol = {"v4": C1, "v5": C2}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.0, 3.3))
    x = np.arange(len(models))
    w = 0.8 / len(vers)
    for vi, v in enumerate(vers):
        off = (vi - (len(vers) - 1) / 2) * w
        p50 = [res.get((v, m), (np.nan,) * 5)[0] for m in models]
        p95 = [res.get((v, m), (np.nan,) * 5)[1] for m in models]
        c = [res.get((v, m), (np.nan,) * 5)[2] for m in models]
        a1.bar(x + off, p50, width=w * 0.9, color=vcol[v], label=f"prompt {v} p50")
        a1.scatter(x + off, p95, marker="_", s=180, color=INK, lw=2, zorder=3,
                   label="p95" if vi == len(vers) - 1 else None)
        a1.vlines(x + off, p50, p95, color=INK, lw=0.8)
        for xi, val in zip(x + off, p95):
            a1.text(xi, val, f"{val:.1f}", ha="center", va="bottom", fontsize=7, color=INK2)
        a2.bar(x + off, c, width=w * 0.9, color=vcol[v], label=f"prompt {v}")
        for xi, val in zip(x + off, c):
            a2.text(xi, val, f"{val:.3f}", ha="center", va="bottom", fontsize=7, color=INK2)
    for a in (a1, a2):
        a.set_xticks(x, models)
        a.grid(axis="x", visible=False)
    a1.set_ylabel("parse latency per LLM call (s)")
    a1.set_title("Latency: bar = p50, tick = p95", loc="left")
    a2.set_ylabel("USD per 100 commands")
    a2.set_title("Cost (logged tokens × list price)", loc="left")
    a1.legend(fontsize=7.5, loc="upper left")
    a2.legend(fontsize=7.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "parser_latency_cost.png")
    plt.close(fig)
    ns = sorted({r[3] for r in res.values()})
    CAPTIONS["parser_latency_cost.png"] = (
        f"LLM command-parser latency (p50 bar, p95 tick; LLM calls only, n = {', '.join(map(str, ns))} per "
        f"model/prompt) and cost per 100 commands (logged prompt/completion tokens × eval/task3_eval.py PRICES, "
        f"USD per 1M tokens; precheck rejects cost 0) on the Standard set (45 commands, 1 run) for prompts "
        f"{' and '.join(vers)}; source {rel(root)}/{{{','.join(vers)}}}/<model>.jsonl.")


# --------------------------------------------------------------------------- Task 2

def fig_turns(args, out):
    d = Path(args.task2_logs)
    before = [r for side in ("left", "right") for r in load_jsonl(d / f"turn_trials_{side}.jsonl")
              if r["mode"] == "closed"]
    after = [r for side in ("left", "right") for r in load_jsonl(d / f"f3_exec_{side}.jsonl")
             if r["mode"] == "exec"]
    lat = load_jsonl(d / "f3_stop_latency.jsonl")
    rows = []
    angles = sorted({abs(r["target_deg"]) for r in before + after})
    grp = {}
    for lab, rs in (("before (closed-loop turn)", before), ("after (F3 executor 45-deg chunks)", after)):
        for a in angles:
            e = [r["abs_error_deg"] for r in rs if abs(r["target_deg"]) == a]
            grp[(lab, a)] = e
            rows.append(["turn_abs_error_deg", lab, a, len(e), f"{statistics.mean(e):.3f}",
                         f"{statistics.stdev(e):.3f}" if len(e) > 1 else "", " ".join(f"{x:.2f}" for x in e)])
    lgrp = {}
    for mode, lab in (("single", "before (single 180-deg turn)"), ("chunked", "after (45-deg chunks)")):
        v = [r["latency_s"] for r in lat if r["mode"] == mode]
        rot = [r["rotation_after_stop_deg"] for r in lat if r["mode"] == mode]
        lgrp[lab] = v
        rows.append(["stop_latency_s", lab, 180, len(v), f"{statistics.mean(v):.3f}",
                     f"{statistics.stdev(v):.3f}" if len(v) > 1 else "", " ".join(f"{x:.3f}" for x in v)])
        rows.append(["rotation_after_stop_deg", lab, 180, len(rot), f"{statistics.mean(rot):.2f}",
                     f"{statistics.stdev(rot):.2f}" if len(rot) > 1 else "", " ".join(f"{x:.1f}" for x in rot)])
    write_csv(out / "turn_accuracy_latency.csv",
              ["metric", "condition", "target_abs_deg", "n", "mean", "std", "values"], rows)

    rng = np.random.default_rng(0)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.0, 3.3), gridspec_kw={"width_ratios": [1.6, 1]})
    labs = list(dict.fromkeys(k[0] for k in grp))
    w = 0.38
    x = np.arange(len(angles))
    for li, (lab, col) in enumerate(zip(labs, (C1, C2))):
        off = (li - 0.5) * w
        means = [statistics.mean(grp[(lab, a)]) for a in angles]
        n = len(grp[(lab, angles[0])])
        a1.bar(x + off, means, width=w * 0.92, color=col, alpha=0.85, label=f"{lab}, n = {n}/angle")
        for xi, a in zip(x + off, angles):
            e = grp[(lab, a)]
            a1.scatter(xi + rng.uniform(-w * 0.25, w * 0.25, len(e)), e, s=10, color=INK, alpha=0.7, zorder=3,
                       lw=0)
    a1.set_xticks(x, [f"{a:g}°" for a in angles])
    a1.set_xlabel("commanded turn (left and right pooled)")
    a1.set_ylabel("|settled heading error| (deg)")
    a1.set_title("Turn accuracy: bar = mean, dots = trials", loc="left")
    a1.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    a1.grid(axis="x", visible=False)
    llabs = list(lgrp)
    for li, (lab, col) in enumerate(zip(llabs, (C1, C2))):
        v = lgrp[lab]
        a2.bar(li, statistics.mean(v), width=0.6, color=col, alpha=0.85)
        a2.scatter(li + rng.uniform(-0.12, 0.12, len(v)), v, s=14, color=INK, zorder=3, lw=0)
        a2.text(li + 0.32, statistics.mean(v), f"mean {statistics.mean(v):.2f} s", ha="left", va="center",
                fontsize=7.5, color=INK2)
    short = {llabs[0]: "before\nsingle turn", llabs[1]: "after\n45° chunks"}
    a2.set_xticks(range(len(llabs)), [f"{short[l]}\nn = {len(lgrp[l])}" for l in llabs], fontsize=7.5)
    a2.set_ylabel("stop latency (s)")
    a2.set_xlim(-0.5, len(llabs) - 0.5 + 0.6)
    a2.set_title("'stop' 0.8 s into a 180° turn", loc="left")
    a2.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(out / "turn_accuracy_latency.png")
    plt.close(fig)
    nb, na = len(before), len(after)
    CAPTIONS["turn_accuracy_latency.png"] = (
        f"Task 2 turns before vs after F3: (left) mean |settled heading error| per commanded angle, left/right "
        f"pooled, closed-loop RealSkills.turn (n = {nb}, {nb // len(angles)} per angle) vs executor 45° chunked "
        f"turns (n = {na}, {na // len(angles)} per angle); (right) stop latency when 'stop' arrives 0.8 s into a "
        f"180° turn, single turn vs chunked (n = {len(lgrp[llabs[0]])} + {len(lgrp[llabs[1]])}); source "
        f"{rel(d)}/turn_trials_*.jsonl, f3_exec_*.jsonl, f3_stop_latency.jsonl.")


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-root", nargs="+", default=[str(REPO / "eval" / "e2e" / "results")],
                    help="dirs holding e2e run dirs (searched in order)")
    ap.add_argument("--s3-runs", nargs="+", help="S3 run names or dirs for figure 1 (+ contacts)")
    ap.add_argument("--allow-partial", action="store_true",
                    help="also use runs with fewer than 10 S3 scenarios (fixfinal / history)")
    ap.add_argument("--parser-root", default=str(REPO / "eval" / "results"))
    ap.add_argument("--v6-root", help="dir holding v6/ and hard/v6/ (default: --parser-root)")
    ap.add_argument("--v6", action="store_true", help="require v6 results (fail if missing)")
    ap.add_argument("--no-v6", action="store_true", help="plot v5 only even if v6 exists")
    ap.add_argument("--task2-logs", default=str(REPO / "docs" / "report_assets" / "task2" / "logs"))
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    runs = all_runs(args.results_root)
    picked = fig_s3_success(args, runs, out)
    fig_s3_history(args, runs, out)
    fig_contacts(args, runs, picked, out)
    fig_parser(args, out)
    fig_turns(args, out)
    fig_latency_cost(args, out)

    order = ["s3_success_ci.png", "s3_history.png", "parser_v5_v6.png", "turn_accuracy_latency.png",
             "contacts.png", "parser_latency_cost.png"]
    lines = ["# Figure captions (generated by make_assets.py; do not edit by hand)", ""]
    lines += [f"- `{k}` — {CAPTIONS[k]}" for k in order if k in CAPTIONS]
    lines += ["", "Regenerate (repo root): `env -u PYTHONPATH .venv/bin/python docs/report_assets/final/make_assets.py "
              + " ".join(sys.argv[1:]).replace(str(REPO) + "/", "") + "`", ""]
    (out / "CAPTIONS.md").write_text("\n".join(lines))
    print(f"\nwrote {len(CAPTIONS)} figures + CSVs + CAPTIONS.md to {rel(out)}")


if __name__ == "__main__":
    main()
