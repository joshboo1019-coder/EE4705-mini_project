# Owner: Student C (Task 4)
# Change contributed by Student B (assist), pending review by Student C
"""
tools/c2_margin_analysis.py — Student B (assist), pending review by Student C.

Range-estimate error at the stop, from real-sim logs. Collects every

    [RANGE] estimated_planar=<est> m ground_truth=<true> m phase=<phase>

line (ground truth is logged by navigation.py for evaluation only) and reports
the error e = true - est for ground-level targets (chairs, the ball) and
elevated ones (stop signs) separately: bias, std, 95th percentile — overall and
in the near band (est <= 1.2 m, where the stop decision is made).

The stop threshold that keeps the TRUE distance <= 0.80 m in >= 95 % of cases
is then  APPROACH_STOP_M = 0.80 - p95(e | near band).

    python tools/c2_margin_analysis.py eval/e2e/results/<run>/   [more runs ...]
        [--json out.json] [--plot out.png]

Target classes come from each run's results.jsonl (S3 scenario metadata).
"""

import argparse
import json
import math
import re
import statistics
from pathlib import Path

RANGE_RE = re.compile(r"\[RANGE\] estimated_planar=([\d.]+) m ground_truth=([\d.]+) m phase=(\w+)")
GROUND = {"chair", "sports ball"}
NEAR_M = 1.2


def collect(run_dirs):
    rows = []
    for d in run_dirs:
        d = Path(d)
        meta = {}
        rj = d / "results.jsonl"
        if rj.exists():
            for line in rj.read_text().splitlines():
                r = json.loads(line)
                if r.get("suite") == "S3":
                    meta[f"S3_{r['scenario']}"] = r.get("meta", {})
        for log in sorted(d.glob("S3_*.log")):
            m = meta.get(log.stem, {})
            target = m.get("target", "")
            cls = target.split("_", 1)[1] if "_" in target else ""
            for line in log.read_text(errors="replace").splitlines():
                g = RANGE_RE.search(line)
                if g:
                    est, true, phase = float(g.group(1)), float(g.group(2)), g.group(3)
                    rows.append({"run": d.name, "scenario": log.stem, "class": cls,
                                 "est": est, "true": true, "err": round(true - est, 3),
                                 "phase": phase})
    return rows


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def stats(errs):
    if not errs:
        return {"n": 0}
    return {"n": len(errs), "bias": round(statistics.mean(errs), 3),
            "std": round(statistics.pstdev(errs), 3),
            "p95": round(pct(errs, 0.95), 3), "max": round(max(errs), 3),
            "min": round(min(errs), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--json")
    ap.add_argument("--plot")
    args = ap.parse_args()
    rows = collect(args.runs)
    ground = [r for r in rows if r["class"] in GROUND]
    elevated = [r for r in rows if r["class"] == "stop sign"]
    out = {
        "ground_all": stats([r["err"] for r in ground]),
        "ground_near": stats([r["err"] for r in ground if r["est"] <= NEAR_M]),
        "ground_stop_check": stats([r["err"] for r in ground if r["phase"] == "stop_check"]),
        "elevated_all": stats([r["err"] for r in elevated]),
        "per_class_near": {c: stats([r["err"] for r in ground if r["class"] == c and r["est"] <= NEAR_M])
                           for c in sorted({r["class"] for r in ground})},
    }
    near = out["ground_near"]
    if near.get("n"):
        out["approach_stop_m"] = round(0.80 - near["p95"], 2)
    print(json.dumps(out, indent=2))
    if args.json:
        Path(args.json).write_text(json.dumps({"summary": out, "rows": rows}, indent=1))
    if args.plot and ground:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(6.4, 4.0))
        for c, mk in (("chair", "o"), ("sports ball", "s")):
            pts = [r for r in ground if r["class"] == c]
            ax.scatter([r["est"] for r in pts], [r["err"] for r in pts], s=12, marker=mk,
                       label=c, alpha=0.7)
        ax.axhline(0, color="grey", lw=0.8)
        ax.axvline(NEAR_M, color="grey", lw=0.8, ls=":")
        ax.set_xlabel("estimated planar distance (m)")
        ax.set_ylabel("true − estimated (m)")
        ax.set_title("Range-estimate error, ground-level targets")
        ax.legend()
        fig.tight_layout()
        fig.savefig(args.plot, dpi=130)


if __name__ == "__main__":
    main()
