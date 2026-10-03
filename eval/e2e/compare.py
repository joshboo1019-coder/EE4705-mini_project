"""
eval/e2e/compare.py — Student B. Baseline vs final e2e comparison.

    python eval/e2e/compare.py <baseline_run_dir> <final_run_dir> [--out eval/e2e/COMPARISON.md]
        [--extra "label=run_dir" ...]

Reads each run's results.jsonl (written by run_all.py) and writes a
per-suite, per-scenario table marked better / worse / same, with the clip of
each row. --extra adds informational columns (e.g. the P2b after-runs).
"""

import argparse
import json
from pathlib import Path


def load(run_dir: Path) -> dict:
    out = {}
    for line in (run_dir / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        out[(r["suite"], r["scenario"])] = r
    return out


def clip(r):
    if not r or not r.get("clip"):
        return "–"
    if (r.get("frame") or {}).get("deleted"):
        return f"~~`{r['clip']}`~~"
    return f"`{r['clip']}`"


def verdict(b, f):
    if b is None:
        return "new"
    if f is None:
        return "–"
    if f > b:
        return "**better**"
    if f < b:
        return "**worse**"
    return "same"


def s3_score(r):
    """Ordering for S3: strict success first, then a correct SUCCESS with a far
    stop, then failures; ties -> same."""
    if r is None:
        return None
    e = r["eval"]
    if e.get("pass"):
        return 2
    return 1 if e.get("mission") == "SUCCESS" else 0


def s3_cell(r):
    if r is None:
        return "–"
    e = r["eval"]
    m = (e.get("mission") or "–").replace("FAIL:", "FAIL ")
    return (f"{'✅' if e.get('pass') else '❌'} {m}, true d {e.get('true_d')}, "
            f"{e.get('time_s')} s{', contact' if e.get('contacts') else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("baseline")
    ap.add_argument("final")
    ap.add_argument("--out", default="eval/e2e/COMPARISON.md")
    ap.add_argument("--extra", nargs="*", default=[])
    args = ap.parse_args()
    B, F = load(Path(args.baseline)), load(Path(args.final))
    extras = []
    for x in args.extra:
        label, d = x.split("=", 1)
        extras.append((label, load(Path(d))))
    bn, fn = Path(args.baseline).name, Path(args.final).name
    L = [f"# e2e comparison: baseline `{bn}` vs final `{fn}`", "",
         f"Baseline = merged main (ee9593f) before tonight's changes, with S3 started by the scenarios.py "
         f"mechanism (main.py had no --scenario yet). Final = `b/overnight-all` (all branches that passed "
         f"their checks; not `assist/stopsign`). Same harness, fresh launch per scenario, real LLM "
         f"(qwen-flash), every scenario recorded: clips under `~/Videos/e2e/`. Per-run details: "
         f"`eval/e2e/results/<run>/summary.md`.", ""]

    # S1
    L += ["## S1 — Task 2 skills (unchanged code: expect same)", "",
          "| Scenario | Baseline | Final | Verdict | Clips (baseline / final) |", "|---|---|---|---|---|"]
    for sc, key, fmt in (("closed", "max_abs_error", "max |err| {}°"),
                         ("open", "mean_abs_error", "mean |err| {}°"),
                         ("move", "distance_m", "{} m")):
        b, f = B.get(("S1", sc)), F.get(("S1", sc))
        bv = b["eval"].get(key) if b else None
        fv = f["eval"].get(key) if f else None
        if sc == "move":
            v = "same" if (bv is not None and fv is not None and abs(bv - fv) <= 0.15) else "different"
        else:
            v = "same" if (bv is not None and fv is not None and abs(bv - fv) <= 1.0) else (
                "**better**" if (fv or 99) < (bv or 99) else "**worse**")
        L.append(f"| {sc} | {fmt.format(bv)} | {fmt.format(fv)} | {v} | {clip(b)} / {clip(f)} |")
    L.append("")

    # S2
    b, f = B.get(("S2", "video_task3")), F.get(("S2", "video_task3"))
    L += ["## S2 — Task 3 (Video_Task3 script a–g typed into main.py)", "",
          "| | Baseline | Final |", "|---|---|---|"]
    for name, g in (("pass", lambda r: r["eval"].get("pass")),
                    ("[CMD] lines as expected", lambda r: sum(c["ok"] for c in r["eval"].get("cmd", []))),
                    ("turn errors (°)", lambda r: r["eval"].get("turn_errors")),
                    ("contacts / fall", lambda r: f"{len(r['eval'].get('contacts', []))} / {r['eval'].get('fall')}"),
                    ("max tilt (°)", lambda r: r["eval"].get("max_tilt_deg")),
                    ("clip", clip)):
        L.append(f"| {name} | {g(b) if b else '–'} | {g(f) if f else '–'} |")
    if f:
        new = [l for _, l in f.get("lines", []) if l.startswith(("[PLAN]", "Robot: "))]
        L += ["", f"Final adds the talk-back lines (prompt v5), e.g. `{new[0] if new else ''}`; "
              "every handout line is unchanged."]
    L.append("")

    # S3
    L += ["## S3 — Task 4 (C's 10 scenarios, typed)", "",
          "Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (10: correct `target_not_found`).", "",
          "| # | Target | Baseline | " + "".join(f"{l} | " for l, _ in extras) +
          "Final | Verdict | Clips (baseline / final) |",
          "|---|---|---|" + "---|" * len(extras) + "---|---|---|"]
    tb = tf = 0
    for i in range(1, 11):
        sc = f"{i:02d}"
        b, f = B.get(("S3", sc)), F.get(("S3", sc))
        tb += bool(b and b["eval"].get("pass"))
        tf += bool(f and f["eval"].get("pass"))
        tgt = (f or b)["meta"]["target"].replace("_", " ")
        ex = "".join(f"{s3_cell(d.get(('S3', sc)))} | " for _, d in extras)
        L.append(f"| {sc} | {tgt} | {s3_cell(b)} | {ex}{s3_cell(f)} | "
                 f"{verdict(s3_score(b), s3_score(f))} | {clip(b)} / {clip(f)} |")
    tex = "".join(f"**{sum(bool(d.get(('S3', f'{i:02d}')) and d[('S3', f'{i:02d}')]['eval'].get('pass')) for i in range(1, 11))}/10** | " for _, d in extras)
    L += [f"| | **strict success** | **{tb}/10** | {tex}**{tf}/10** | | |", ""]

    # S4
    L += ["## S4 — Bonus", ""]
    b, f = B.get(("S4", "look")), F.get(("S4", "look"))
    L += ["| Look question | Baseline answer | Final answer |", "|---|---|---|"]
    qs = ["what can you see? (after turn around)", "is there a chair in front of you? (after turn right 45)",
          "what colour is the ball ahead? (after turn left 90)"]
    ba = (b["eval"].get("answers") if b else []) + ["–"] * 3
    fa = (f["eval"].get("answers") if f else []) + ["–"] * 3
    # the final run also prints talk-back "Robot: Done: ..." lines after turns: keep VLM answers only
    fa = [a for a in fa if not a.startswith("Done:")] + ["–"] * 3
    for q, x, y in zip(qs, ba, fa):
        L.append(f"| {q} | {x[:160]} | {y[:160]} |")
    L += ["", f"Clips: {clip(b)} / {clip(f)}. Correctness checked by hand against the saved frames "
          "(see MORNING_BRIEF.md).", ""]
    b, f = B.get(("S4", "multigoal")), F.get(("S4", "multigoal"))
    L += ["| Multi-goal (red chair, then orange ball) | Baseline | Final |", "|---|---|---|",
          f"| `[MULTI]` | `{b['eval'].get('multi') if b else '–'}` | `{f['eval'].get('multi') if f else '–'}` |",
          f"| true d at stops | {b['eval'].get('true_d_at_stops') if b else '–'} | "
          f"{f['eval'].get('true_d_at_stops') if f else '–'} |",
          f"| strict C2 (all ≤ 0.80 m) | {b['eval'].get('strict_c2') if b else '–'} | "
          f"{f['eval'].get('strict_c2') if f else '–'} |",
          f"| clip | {clip(b)} | {clip(f)} |", ""]

    # S5
    L += ["## S5 — B upgrades (final only; new features)", "",
          "| Scenario | Checks | Pass | Clip |", "|---|---|---|---|"]
    for (s, sc), r in sorted(F.items()):
        if s != "S5":
            continue
        e = r["eval"]
        chk = ", ".join(f"{k} {'✅' if v else '❌'}" for k, v in (e.get("checks") or {}).items())
        if e.get("estop_latency_ms") is not None:
            chk += f", [ESTOP] software latency {e['estop_latency_ms']} ms"
        L.append(f"| {sc} | {chk} | {'✅' if e.get('pass') else '❌'} | {clip(r)} |")
    L.append("")
    Path(args.out).write_text("\n".join(L))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
