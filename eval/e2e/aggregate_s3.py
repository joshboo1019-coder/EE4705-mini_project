"""
eval/e2e/aggregate_s3.py — Student B. S3 over repeated runs (n per scenario).

    python eval/e2e/aggregate_s3.py "baseline=dirA,dirB,dirC" "final=dirD,dirE,dirF" [--out file.md]

Per scenario: strict successes / runs and the true distances at the stop; per
target class: strict success rate, mean / max true d of SUCCESS stops, how many
"SUCCESS" stops violated C2 (true d > 0.80 m), stop_verification failures, and
runs with contact. Ground truth comes from each run's trace (logging only).
"""

import argparse
import json
import statistics
from pathlib import Path


def load(d):
    out = {}
    for line in (Path(d) / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["suite"] == "S3":
            out[r["scenario"]] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("groups", nargs="+")
    ap.add_argument("--out")
    args = ap.parse_args()
    groups = []
    for g in args.groups:
        label, dirs = g.split("=", 1)
        groups.append((label, [load(d) for d in dirs.split(",")]))
    L = ["| # | Target | " + " | ".join(f"{l} (n={len(runs)})" for l, runs in groups) + " |",
         "|---|---|" + "---|" * len(groups)]
    for i in range(1, 11):
        sc = f"{i:02d}"
        tgt = groups[0][1][0][sc]["meta"]["target"].replace("_", " ")
        cells = []
        for _, runs in groups:
            rs = [r[sc] for r in runs if sc in r]
            ok = sum(bool(r["eval"].get("pass")) for r in rs)
            ds = ", ".join(str(r["eval"].get("true_d")) for r in rs)
            cells.append(f"{ok}/{len(rs)} (true d {ds})")
        L.append(f"| {sc} | {tgt} | " + " | ".join(cells) + " |")
    tot = []
    for _, runs in groups:
        n = sum(1 for r in runs for _ in r)
        ok = sum(bool(x["eval"].get("pass")) for r in runs for x in r.values())
        tot.append(f"**{ok}/{n}** ({100 * ok / n:.0f} %)")
    L += ["| | **all** | " + " | ".join(tot) + " |", ""]

    L += ["| Class | " + " | ".join(l for l, _ in groups) + " |", "|---|" + "---|" * len(groups)]
    for cls in ("chair", "sports ball", "stop sign"):
        cells = []
        for _, runs in groups:
            rs = [x for r in runs for x in r.values()
                  if x["meta"]["target"].split("_", 1)[1] == cls and not x["meta"]["expected"].startswith("FAIL")]
            ok = sum(bool(x["eval"].get("pass")) for x in rs)
            succ = [x["eval"]["true_d"] for x in rs if x["eval"].get("mission") == "SUCCESS"
                    and x["eval"].get("true_d") is not None]
            c2bad = sum(1 for d in succ if d > 0.80)
            sv = sum(1 for x in rs if x["eval"].get("mission") == "FAIL:stop_verification")
            cont = sum(1 for x in rs if x["eval"].get("contacts"))
            md = f"{statistics.mean(succ):.2f}/{max(succ):.2f}" if succ else "–"
            cells.append(f"strict {ok}/{len(rs)}; SUCCESS {len(succ)} (true d mean/max {md}, "
                         f"{c2bad} > 0.80 m); stop_verification {sv}; contact {cont}")
        L.append(f"| {cls} | " + " | ".join(cells) + " |")
    text = "\n".join(L)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
