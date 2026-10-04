# Owner: Student B (bonus: visual QA)
"""
[B] tools/vlm_scaled_eval.py — scaled offline comparison of the VLM
(config.VLM_SERVICE, qwen3-vl-flash) against YOLO + colour grounding
(perception_real.RealPerception, Task 4 config) on ~30 onboard 640x480
dog_front_camera frames. Written by Student B.

Offline only: no simulator, no control code. Ground truth (scenario layouts,
segmentation pixel counts, hand labels) is used ONLY to score, never by the
robot.

Frames come from two places (see eval/vlm_eval.md, "Scaled comparison"):
  real  frames the runtime saved during real-sim runs (look action, VLM
        probes, Task 2 camera evidence). Labelled by hand from the image.
  rend  frames from tools/task4_color_testset.py `render` on the main scene
        (square "+" sign plates). Labelled from the MuJoCo segmentation
        pixel counts stored in its frames.json (objects[*].seen_px).

  python tools/vlm_scaled_eval.py run    --render-dir DIR [--budget 0.10]
  python tools/vlm_scaled_eval.py report

`run` calls the VLM once per frame (resumable: frames already in the results
file are skipped) and stops before the budget is spent. `report` writes the
CSV + figure under docs/report_assets/final/ and prints the markdown tables.
"""

import argparse
import base64
import io
import json
import random
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import config  # noqa: E402

OUT_DIR = ROOT / "eval" / "results" / "vlm" / "scaled"
RESULTS = OUT_DIR / "results.jsonl"
ASSETS = ROOT / "docs" / "report_assets" / "final"
CSV_PATH = ASSETS / "vlm_vs_yolo_scaled.csv"
PNG_PATH = ASSETS / "vlm_vs_yolo_scaled.png"

# qwen3-vl-flash, Alibaba Model Studio international (Singapore), 0-32K tier,
# USD per 1M tokens (input, output); same source as eval/vlm_eval.md.
PRICE_IN, PRICE_OUT = 0.05, 0.40

TASK_CLASSES = ("chair", "stop sign", "sports ball")
COLOURS = ("red", "green", "yellow", "orange", "blue")
MIN_SEEN_PX = 400        # rendered: >= this many visible pixels -> must be found
                         # 1..399 px -> "marginal" (not required, not an FP)

# ---------------------------------------------------------------------------
# Frame set
# ---------------------------------------------------------------------------

# Real runtime frames, labelled by hand from the image (Student B, 2026-10-04).
# expected = clearly visible; marginal = cut by the frame edge / mostly hidden.
_RS = "red stop sign"
REAL_FRAMES = [
    ("eval/results/vlm/20261002-232010-231387.png", "look session 2026-10-02 (real_sim_check.log), look 1",
     ["red chair", _RS, "green stop sign", "yellow stop sign"], ["orange sports ball", "green chair"]),
    ("eval/results/vlm/20261002-232018-702459.png", "look session 2026-10-02 (real_sim_check.log), look 2",
     ["green chair", "orange sports ball", "yellow stop sign"], [_RS]),
    ("eval/results/vlm/20261002-232027-560433.png", "look session 2026-10-02 (real_sim_check.log), look 3",
     [], []),
    ("eval/results/vlm/20261004-010952-986951.png", "e2e 20261004-0101_baseline S4_look, look 3",
     ["red chair", "green stop sign"], []),
    ("eval/results/vlm/probe_frame_spawn.png", "VLM probe frame (spawn, task3_eval.md 'VLM choice')",
     ["blue chair"], []),
    ("eval/results/vlm/probe_frame_turned_around.png", "VLM probe frame (turned around)",
     [_RS, "green stop sign", "yellow stop sign"], ["red chair", "green chair", "orange sports ball"]),
    ("docs/report_assets/task2/yolo_screenshots/raw/yolo_01_overview_both_chairs.png", "Task 2 camera evidence, overview",
     ["red chair", "green chair", _RS, "green stop sign", "yellow stop sign"], ["orange sports ball"]),
    ("docs/report_assets/task2/yolo_screenshots/raw/yolo_02_green_chair_1p6m.png", "Task 2 camera evidence, green chair 1.6 m",
     ["green chair", "yellow stop sign"], []),
    ("docs/report_assets/task2/yolo_screenshots/raw/yolo_03_red_chair_1p6m.png", "Task 2 camera evidence, red chair 1.6 m",
     ["red chair", "green stop sign"], []),
    ("docs/report_assets/task2/yolo_screenshots/raw/yolo_04_ball_1p6m.png", "Task 2 camera evidence, ball 1.6 m",
     ["orange sports ball", "green stop sign"], []),
    ("docs/report_assets/task2/yolo_screenshots/raw/yolo_05_green_chair_side_1p6m.png", "Task 2 camera evidence, green chair side",
     ["green chair"], []),
    ("docs/report_assets/task2/yolo_screenshots/raw/yolo_06_yellow_stop_sign_1p8m.png", "Task 2 camera evidence, yellow sign 1.8 m",
     ["yellow stop sign"], []),
]

# Hand check of the rendered picks: signs whose seen_px is (mostly) the grey
# pole, with the coloured plate out of view -> marginal, not required.
PLATE_OUT_OF_VIEW = {}   # none left once the sign views start at 1.1 m

# e2e S3 scenario whose goal object a rendered view corresponds to
S3_FOR = {"red_chair": "S3_01/S3_04", "orange_sports ball": "S3_02/S3_07", "green_chair": "S3_03",
          "yellow_stop sign": "S3_05", "green_stop sign": "S3_06", "blue_chair": "S3_08/S3_10",
          "red_stop sign": "S3_09"}


def _key_to_obj(key: str) -> str:            # "red_stop sign" -> "red stop sign"
    return key.replace("_", " ")


def rendered_frames(render_dir: Path):
    """Stratified, seeded pick from the main-scene render set:
    stop signs (3 colours x 3 ranges), close-range red chair (0.8 m, incl.
    the view where YOLO says 'bed'), and 4 others."""
    rng = random.Random(4705)
    meta = {}
    for split in ("tune", "hold"):
        for f in json.loads((render_dir / split / "frames.json").read_text()):
            meta[(split, f["frame"])] = f

    def pick(target, dists, n, must=()):
        pool = sorted(k for k, f in meta.items() if f["target"] == target and f["dist"] in dists
                      and k not in must)
        return list(must) + rng.sample(pool, n - len(must))

    chosen = []
    for sign in ("red_stop sign", "yellow_stop sign", "green_stop sign"):
        # not 0.8 m: there the plate (z = 0.85 m) is above the camera's view
        # and only the grey pole is in frame, which nobody can colour
        for dists in ((1.1,), (1.4, 1.7), (2.3, 2.5)):
            chosen += [("stop sign", k) for k in pick(sign, dists, 1)]
    chosen += [("close red chair", k) for k in pick("red_chair", (0.8,), 6, must=[("tune", "0036.png")])]
    chosen += [("other", k) for k in pick("green_chair", (0.8,), 2)]
    chosen += [("other", k) for k in pick("blue_chair", (0.8,), 1, must=[("tune", "0068.png")])]
    chosen += [("other", k) for k in pick("orange_sports ball", (1.4,), 1)]

    out = []
    for subset, (split, name) in chosen:
        f = meta[(split, name)]
        demote = set(PLATE_OUT_OF_VIEW.get(f"rend_{split}_{name[:-4]}", ()))
        exp = sorted(_key_to_obj(k) for k, o in f["objects"].items()
                     if o["seen_px"] >= MIN_SEEN_PX and _key_to_obj(k) not in demote)
        marg = sorted(_key_to_obj(k) for k, o in f["objects"].items()
                      if 0 < o["seen_px"] < MIN_SEEN_PX or _key_to_obj(k) in demote)
        x, y, _, yaw = f["pose"]
        out.append(dict(
            id=f"rend_{split}_{name[:-4]}", source="rendered", subset=subset,
            path=str(render_dir / split / "frames" / name),
            scenario=f"{S3_FOR[f['target']]} goal view: {_key_to_obj(f['target'])} at {f['dist']} m, "
                     f"bearing {f['bearing_deg']:.1f} deg (pose x={x:.2f} y={y:.2f} yaw={yaw:.0f})",
            expected=exp, marginal=marg, labels="segmentation seen_px"))
    return out


def _real_path(p: str) -> Path:
    """Frames saved by the runtime are git-ignored: in a worktree, fall back
    to the main checkout's copy."""
    for base in (ROOT, ROOT.parent.parent):
        if (base / p).exists():
            return base / p
    raise FileNotFoundError(p)


def frame_set(render_dir: Path):
    real = [dict(id="real_" + Path(p).stem, source="real",
                 subset="stop sign" if p.endswith("yellow_stop_sign_1p8m.png") else "real",
                 path=str(_real_path(p)), scenario=s, expected=sorted(e), marginal=sorted(m), labels="hand")
            for p, s, e, m in REAL_FRAMES]
    return real + rendered_frames(render_dir)

# ---------------------------------------------------------------------------
# VLM: the project's client and model (dialogue.vlm / llm_parser), with a
# detection prompt instead of the free-text QA prompt.
# ---------------------------------------------------------------------------

VLM_PROMPT = (
    "You are the eyes of a small quadruped robot dog. The image is the current view from its "
    "640x480 front camera. List every distinct object you can see. Ignore the floor, the sky and "
    "terrain (stairs, steps, ramps, slabs, rocks or rubble). A sign and its pole are one object. "
    "For each object give a short noun label, its main colour and a bounding box "
    "[x1, y1, x2, y2]. Reply with JSON only, no prose: "
    '{"objects": [{"label": "...", "color": "...", "bbox": [x1, y1, x2, y2]}]}. '
    'If there are no objects, reply {"objects": []}. Report only what is visible in this image.')


def vlm_detect(frame: np.ndarray):
    from dialogue import llm_parser, vlm
    provider, model, extra = vlm.VLM_SERVICES[config.VLM_SERVICE]
    client = llm_parser._get_client(provider)
    messages = [{"role": "user", "content": [
        {"type": "text", "text": VLM_PROMPT},
        {"type": "image_url", "image_url": {"url": vlm._png_data_url(frame)}}]}]
    t0 = time.time()
    resp = client.chat.completions.create(model=model, messages=messages, **extra)
    latency = time.time() - t0
    text = (resp.choices[0].message.content or "").strip()
    usage = getattr(resp, "usage", None)
    tin = getattr(usage, "prompt_tokens", 0) or 0
    tout = getattr(usage, "completion_tokens", 0) or 0
    return dict(model=model, raw=text, latency_s=latency, tokens_in=tin, tokens_out=tout,
                cost_usd=(tin * PRICE_IN + tout * PRICE_OUT) / 1e6, objects=parse_vlm(text))


def parse_vlm(text: str):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        objs = json.loads(m.group(0))["objects"] if m else []
    except (ValueError, KeyError, TypeError):
        objs = []
    return [dict(label=str(o.get("label", "")), color=str(o.get("color", "")), bbox=o.get("bbox"))
            for o in objs if isinstance(o, dict)]


def vlm_class(label: str) -> str:
    s = label.lower()
    if re.search(r"chair|seat|stool", s):
        return "chair"
    if re.search(r"sign|plate|board|placard|panel|flag", s):
        return "stop sign"       # the scene's only signs are the three "stop signs"
    if re.search(r"ball|sphere|orb", s):
        return "sports ball"
    return "other"


def norm_colour(c: str) -> str:
    s = c.lower().replace("gold", "yellow")
    hits = [(s.find(k), k) for k in COLOURS if k in s]
    return min(hits)[1] if hits else "unknown"

# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def cmd_run(a):
    from perception.perception_real import RealPerception
    import contextlib
    frames = frame_set(Path(a.render_dir))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "frames.json").write_text(json.dumps(frames, indent=1))
    done = {json.loads(l)["id"] for l in RESULTS.open()} if RESULTS.exists() else set()
    spent = sum(json.loads(l)["vlm"]["cost_usd"] for l in RESULTS.open()) if RESULTS.exists() else 0.0
    perc = RealPerception(config.YOLO_MODEL)
    with contextlib.redirect_stdout(io.StringIO()):
        perc.detect(np.zeros((480, 640, 3), np.uint8))         # warm-up, not timed
    for fr in frames:
        if fr["id"] in done:
            continue
        if spent > a.budget:
            print(f"[BUDGET] stop: ${spent:.4f} > ${a.budget}")
            break
        frame = np.asarray(Image.open(fr["path"]).convert("RGB"))
        assert frame.shape == (480, 640, 3), fr["path"]
        t0 = time.time()
        with contextlib.redirect_stdout(io.StringIO()):
            dets = perc.detect(frame)
        yolo_t = time.time() - t0
        v = vlm_detect(frame)
        spent += v["cost_usd"]
        row = dict(id=fr["id"], yolo_latency_s=yolo_t,
                   yolo=[dict(cls=d.class_name, color=d.color, conf=round(d.conf, 3),
                              bbox=[round(x, 1) for x in d.bbox]) for d in dets], vlm=v)
        with RESULTS.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"{fr['id']:<40} yolo={[(d.class_name, d.color) for d in dets]} "
              f"vlm={[(o['label'], o['color']) for o in v['objects']]} "
              f"t={v['latency_s']:.2f}s tok={v['tokens_in']}/{v['tokens_out']} spent=${spent:.5f}")

# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def _pairs_yolo(dets):
    task = {f"{d['color']} {d['cls']}" for d in dets if d["cls"] in TASK_CLASSES}
    other = sorted({f"{d['cls']}" for d in dets if d["cls"] not in TASK_CLASSES})
    return task, other


# real scene structure the VLM sometimes lists although told not to: not an
# error, not counted. Any other non-task label (e.g. "table" for a chair) is a
# wrong-class label, like YOLO's "bed" / "umbrella".
STRUCTURE = re.compile(r"pole|stair|step|platform|ramp|slab|rock|rubble|terrain|floor")


def _pairs_vlm(objs):
    task, other = set(), []
    for o in objs:
        c = vlm_class(o["label"])
        if c == "other":
            if not STRUCTURE.search(o["label"].lower()):
                other.append(o["label"])
        else:
            task.add(f"{norm_colour(o['color'])} {c}")
    return task, sorted(set(other))


def score(frames, results):
    rows = []
    for fr in frames:
        r = results.get(fr["id"])
        if r is None:
            continue
        exp, marg = set(fr["expected"]), set(fr["marginal"])
        out = dict(fr=fr, r=r)
        for who, (task, other) in (("yolo", _pairs_yolo(r["yolo"])), ("vlm", _pairs_vlm(r["vlm"]["objects"]))):
            out[who] = dict(
                pred=sorted(task), other=other,
                hit={e: e in task for e in exp},
                fp=sorted(p for p in task if p not in exp | marg))
        rows.append(out)
    return rows


def _rate(h, n):
    return f"{h}/{n} ({100 * h / n:.0f}%)" if n else "–"


def cmd_report(a):
    import csv
    frames = json.loads((OUT_DIR / "frames.json").read_text())
    results = {json.loads(l)["id"]: json.loads(l) for l in RESULTS.open()}
    rows = score(frames, results)
    ASSETS.mkdir(parents=True, exist_ok=True)

    # --- CSV: one row per frame
    with CSV_PATH.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["frame_id", "frame_path", "source", "subset", "scenario", "label_method",
                    "expected_objects", "marginal_objects",
                    "yolo_detections", "yolo_hits", "yolo_misses", "yolo_false_pos", "yolo_wrong_class_labels",
                    "vlm_detections", "vlm_hits", "vlm_misses", "vlm_false_pos", "vlm_wrong_class_labels",
                    "yolo_latency_s", "vlm_latency_s", "vlm_tokens_in", "vlm_tokens_out", "vlm_cost_usd"])
        for x in rows:
            fr, r = x["fr"], x["r"]
            path = fr["path"].replace(str(ROOT) + "/", "")
            if fr["source"] == "rendered":
                path = "render:" + "/".join(Path(path).parts[-3:])
            yd = "; ".join(f"{d['color']} {d['cls']} {d['conf']:.2f}" for d in r["yolo"])
            vd = "; ".join(f"{o['color']} {o['label']}" for o in r["vlm"]["objects"])
            w.writerow([fr["id"], path, fr["source"], fr["subset"], fr["scenario"], fr["labels"],
                        "; ".join(fr["expected"]), "; ".join(fr["marginal"]),
                        yd, "; ".join(k for k, v in x["yolo"]["hit"].items() if v),
                        "; ".join(k for k, v in x["yolo"]["hit"].items() if not v),
                        "; ".join(x["yolo"]["fp"]), "; ".join(x["yolo"]["other"]),
                        vd, "; ".join(k for k, v in x["vlm"]["hit"].items() if v),
                        "; ".join(k for k, v in x["vlm"]["hit"].items() if not v),
                        "; ".join(x["vlm"]["fp"]), "; ".join(x["vlm"]["other"]),
                        f"{r['yolo_latency_s']:.3f}", f"{r['vlm']['latency_s']:.2f}",
                        r["vlm"]["tokens_in"], r["vlm"]["tokens_out"], f"{r['vlm']['cost_usd']:.6f}"])

    # --- per class/colour recall
    objs = ["red chair", "green chair", "blue chair", "orange sports ball",
            "red stop sign", "yellow stop sign", "green stop sign"]
    per = {}
    for o in objs:
        n = sum(o in x["fr"]["expected"] for x in rows)
        per[o] = dict(n=n, **{f"{w}_hit": sum(x[w]["hit"].get(o, False) for x in rows)
                               for w in ("yolo", "vlm")})
    tot_n = sum(p["n"] for p in per.values())

    def tot(w, k="hit", sel=lambda x: True, objf=lambda e: True):
        return sum(v for x in rows if sel(x) for e, v in x[w][k].items() if objf(e))

    def cnt(sel=lambda x: True, objf=lambda e: True):
        return sum(1 for x in rows if sel(x) for e in x["fr"]["expected"] if objf(e))

    print(f"n frames = {len(rows)} (real {sum(x['fr']['source'] == 'real' for x in rows)}, "
          f"rendered {sum(x['fr']['source'] == 'rendered' for x in rows)}); expected objects = {tot_n}\n")
    print("| Object (class + colour) | n visible | YOLO recall | VLM recall |")
    print("|---|---|---|---|")
    for o, p in per.items():
        print(f"| {o} | {p['n']} | {_rate(p['yolo_hit'], p['n'])} | {_rate(p['vlm_hit'], p['n'])} |")
    print(f"| **all** | {tot_n} | **{_rate(tot('yolo'), tot_n)}** | **{_rate(tot('vlm'), tot_n)}** |")

    fp = {w: sum(len(x[w]["fp"]) for x in rows) for w in ("yolo", "vlm")}
    oth = {w: sum(len(x[w]["other"]) for x in rows) for w in ("yolo", "vlm")}
    oth_list = {w: sorted({o for x in rows for o in x[w]["other"]}) for w in ("yolo", "vlm")}
    fp_frames = {w: sum(bool(x[w]["fp"]) for x in rows) for w in ("yolo", "vlm")}
    print(f"\nFP (task class+colour not in the frame): YOLO {fp['yolo']} in {fp_frames['yolo']} frames, "
          f"VLM {fp['vlm']} in {fp_frames['vlm']} frames")
    print(f"wrong-class labels: YOLO {oth['yolo']} {oth_list['yolo']}; VLM {oth['vlm']} {oth_list['vlm']}")
    print("FP details:", [(x["fr"]["id"], w, x[w]["fp"]) for x in rows for w in ("yolo", "vlm") if x[w]["fp"]])

    is_sign = lambda e: e.endswith("stop sign")     # noqa: E731
    sub_sign = lambda x: x["fr"]["subset"] == "stop sign"     # noqa: E731
    sub_chair = lambda x: x["fr"]["subset"] == "close red chair"     # noqa: E731
    subsets = {
        "stop-sign frames: signs": (sub_sign, is_sign),
        "all frames: signs": (lambda x: True, is_sign),
        "close-range red chair frames: red chair": (sub_chair, lambda e: e == "red chair"),
        "close-range red chair frames: all objects": (sub_chair, lambda e: True),
        "real frames: all objects": (lambda x: x["fr"]["source"] == "real", lambda e: True),
        "rendered frames: all objects": (lambda x: x["fr"]["source"] == "rendered", lambda e: True),
    }
    print("\n| Subset | n frames | n objects | YOLO | VLM |\n|---|---|---|---|---|")
    sub_vals = {}
    for name, (sel, objf) in subsets.items():
        n = cnt(sel, objf)
        nf = sum(sel(x) for x in rows)
        sub_vals[name] = (tot("yolo", "hit", sel, objf), tot("vlm", "hit", sel, objf), n)
        print(f"| {name} | {nf} | {n} | {_rate(sub_vals[name][0], n)} | {_rate(sub_vals[name][1], n)} |")
    chair_rows = [x for x in rows if sub_chair(x)]
    print("close chair YOLO labels:", [(x["fr"]["id"], [(d["cls"], d["color"], d["conf"]) for d in x["r"]["yolo"]])
                                       for x in chair_rows])
    print("close chair VLM labels:", [(x["fr"]["id"], [(o["label"], o["color"]) for o in x["r"]["vlm"]["objects"]])
                                      for x in chair_rows])

    lat_y = np.array([x["r"]["yolo_latency_s"] for x in rows])
    lat_v = np.array([x["r"]["vlm"]["latency_s"] for x in rows])
    tin = np.array([x["r"]["vlm"]["tokens_in"] for x in rows])
    tout = np.array([x["r"]["vlm"]["tokens_out"] for x in rows])
    cost = sum(x["r"]["vlm"]["cost_usd"] for x in rows)
    print(f"\nlatency YOLO median {np.median(lat_y):.3f} s p90 {np.percentile(lat_y, 90):.3f}; "
          f"VLM median {np.median(lat_v):.2f} s p90 {np.percentile(lat_v, 90):.2f} max {lat_v.max():.2f}")
    print(f"VLM tokens in/out mean {tin.mean():.0f}/{tout.mean():.0f}; total cost ${cost:.5f} "
          f"(${cost / len(rows):.6f}/frame)")
    parse_fail = [x["fr"]["id"] for x in rows if not x["r"]["vlm"]["objects"] and "objects" not in x["r"]["vlm"]["raw"]]
    print("VLM unparsable answers:", parse_fail)

    figure(per, sub_vals, fp, oth, len(rows), tot_n)


def figure(per, sub_vals, fp, oth, n_frames, tot_n):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ink, ink2, grid, surf = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    c_y, c_v = "#2a78d6", "#eb6834"          # categorical slots 1, 2
    plt.rcParams.update({"font.size": 8, "axes.edgecolor": ink2, "axes.labelcolor": ink2,
                         "xtick.color": ink2, "ytick.color": ink2, "text.color": ink})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.0), gridspec_kw={"width_ratios": [1.35, 1]},
                                   facecolor=surf)
    labels = [f"{o.replace('sports ', '').replace('stop ', '')} (n={p['n']})" for o, p in per.items()]
    yv = [100 * p["yolo_hit"] / p["n"] if p["n"] else 0 for p in per.values()]
    vv = [100 * p["vlm_hit"] / p["n"] if p["n"] else 0 for p in per.values()]
    labels.append(f"all (n={tot_n})")
    yv.append(100 * sum(p["yolo_hit"] for p in per.values()) / tot_n)
    vv.append(100 * sum(p["vlm_hit"] for p in per.values()) / tot_n)
    _bars(ax1, labels, yv, vv, c_y, c_v, surf)
    ax1.set_title("Recall by object (class + colour)", fontsize=9, loc="left", color=ink)
    sl = {"stop-sign frames: signs": "stop-sign frames",
          "close-range red chair frames: red chair": "close red chair (0.8 m)",
          "real frames: all objects": "real runtime frames",
          "rendered frames: all objects": "rendered frames"}
    s_lab = [f"{sl[k]} (n={sub_vals[k][2]})" for k in sl]
    _bars(ax2, s_lab, [100 * sub_vals[k][0] / sub_vals[k][2] for k in sl],
          [100 * sub_vals[k][1] / sub_vals[k][2] for k in sl], c_y, c_v, surf)
    ax2.set_title("Recall by subset", fontsize=9, loc="left", color=ink)
    for ax in (ax1, ax2):
        ax.set_facecolor(surf)
        ax.set_xlim(0, 112)
        ax.set_xlabel("recall (%)")
        ax.grid(axis="x", color=grid, lw=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    h = [plt.Rectangle((0, 0), 1, 1, color=c_y), plt.Rectangle((0, 0), 1, 1, color=c_v)]
    fig.legend(h, [f"YOLO yolo11n + colour (FP {fp['yolo']}, wrong-class labels {oth['yolo']})",
                   f"VLM qwen3-vl-flash (FP {fp['vlm']}, wrong-class labels {oth['vlm']})"],
               loc="lower center", ncol=2, frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(f"VLM vs YOLO on {n_frames} onboard 640x480 frames", fontsize=10, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.07, 1, 0.97))
    fig.savefig(PNG_PATH, dpi=300, facecolor=surf)
    print("wrote", PNG_PATH, CSV_PATH)


def _bars(ax, labels, a, b, ca, cb, surf):
    y = np.arange(len(labels))[::-1]
    h = 0.38
    ax.barh(y + h / 2, a, h, color=ca, edgecolor=surf, linewidth=1)
    ax.barh(y - h / 2, b, h, color=cb, edgecolor=surf, linewidth=1)
    for yy, va, vb in zip(y, a, b):
        ax.text(va + 1.5, yy + h / 2, f"{va:.0f}", va="center", fontsize=6.5, color="#52514e")
        ax.text(vb + 1.5, yy - h / 2, f"{vb:.0f}", va="center", fontsize=6.5, color="#52514e")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--render-dir", required=True, help="task4_color_testset.py render output (main scene)")
    r.add_argument("--budget", type=float, default=0.10, help="USD; stop before spending more")
    sub.add_parser("report")
    a = ap.parse_args()
    {"run": cmd_run, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    main()
