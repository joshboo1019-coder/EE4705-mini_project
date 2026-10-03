"""
tools/task4_stopsign_eval.py -- stop-sign detection rate before/after the
octagonal STOP plate. Written by Student B (assist), pending review by
Student C. OFFLINE EVALUATION ONLY (ground truth labels detections here and
nowhere else).

A thin wrapper around tools/task4_color_testset.py (same viewpoints, same
YOLO settings: config.YOLO_MODEL, conf config.YOLO_CONF_THRESHOLD, imgsz
config.YOLO_IMGSZ) with two additions:
  * --scene: render any scene file (e.g. the pre-change custom_scene.xml
    saved with `git show ee9593f:assets/scenes/custom_scene.xml > old.xml`;
    keep it inside assets/scenes/ or give its textures absolute paths);
  * mesh geoms (the octagon plate) get their projected box from MuJoCo's
    geom_aabb, so the "visible" test also covers the plate.

    git show ee9593f:assets/scenes/custom_scene.xml > assets/scenes/_old_signs.xml
    MUJOCO_GL=egl python tools/task4_stopsign_eval.py run --scene assets/scenes/_old_signs.xml --out BASE
    MUJOCO_GL=egl python tools/task4_stopsign_eval.py run --out NEW          # current scene
    python tools/task4_stopsign_eval.py report --out NEW --ref BASE
    python tools/task4_stopsign_eval.py montage --out NEW --ref BASE --dest docs/task4_stopsign_crops.png

`run` renders the tuning and held-out sets into DIR/tune and DIR/hold and
runs detection. `report` prints, per sign colour, the detection rate as
"stop sign" (and as any class), and how often the colour grounding names
the sign's colour; with --ref it also scores DIR on exactly the frames where
the sign was visible in the reference (baseline) run.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import task4_color_testset as ts  # noqa: E402

SIGNS = ("red_stop sign", "yellow_stop sign", "green_stop sign")
SETS = (("tune", False), ("hold", True))

_orig_corners = ts._geom_corners


def _geom_corners(mujoco, model, data, g):
    if model.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH:
        return _orig_corners(mujoco, model, data, g)
    c, half = model.geom_aabb[g][:3], model.geom_aabb[g][3:]
    signs = np.array([[a, b, cc] for a in (-1, 1) for b in (-1, 1) for cc in (-1, 1)])
    local = c + signs * half
    return data.geom_xpos[g] + local @ data.geom_xmat[g].reshape(3, 3).T


ts._geom_corners = _geom_corners


def run(scene: Path, out: Path):
    import skills.skills_real as sr
    orig = sr.RealSkills
    sr.RealSkills = lambda gui=False: orig(scene_path=str(scene.resolve()), gui=gui)
    try:
        for name, hold in SETS:
            ts.render(out / name, holdout=hold)
    finally:
        sr.RealSkills = orig
    for name, _ in SETS:
        ts.detect(out / name, ts.config.YOLO_MODEL, "yolo11n")


def _load(out: Path):
    sets = {}
    for name, _ in SETS:
        meta = json.loads((out / name / "frames.json").read_text())
        rows = [json.loads(l) for l in (out / name / "detections_yolo11n.jsonl").open()]
        sets[name] = (meta, rows)
    return sets


def report(out: Path, ref: Path = None):
    cur = _load(out)
    base = _load(ref) if ref else None
    res = {}
    for key in SIGNS:
        colour = key.split("_")[0]
        r = dict(vis=0, hit=0, any=0, ref_vis=0, ref_hit=0, ref_any=0,
                 n_ss=0, ss_col_ok=0, ss_col={}, n_lab=0, lab_col_ok=0)
        for name, _ in SETS:
            meta, rows = cur[name]
            by_frame = {}
            for row in rows:
                by_frame.setdefault(row["frame"], []).append(row)
            ref_vis = None
            if base:
                ref_vis = {m["frame"] for m in base[name][0] if ts._visible(m["objects"].get(key))}
            for m in meta:
                dets = [d for d in by_frame.get(m["frame"], []) if d["truth"] == key]
                hit = any(d["cls"] == "stop sign" for d in dets)
                if ts._visible(m["objects"].get(key)):
                    r["vis"] += 1
                    r["hit"] += hit
                    r["any"] += bool(dets)
                if ref_vis is not None and m["frame"] in ref_vis:
                    r["ref_vis"] += 1
                    r["ref_hit"] += hit
                    r["ref_any"] += bool(dets)
            for d in rows:
                if d["truth"] != key:
                    continue
                r["n_lab"] += 1
                r["lab_col_ok"] += d["color_main"] == colour
                if d["cls"] == "stop sign":
                    r["n_ss"] += 1
                    r["ss_col_ok"] += d["color_main"] == colour
                    r["ss_col"][d["color_main"]] = r["ss_col"].get(d["color_main"], 0) + 1
        res[key] = r
    tot = {k: sum(r[k] for r in res.values() if isinstance(r[k], int)) for k in res[SIGNS[0]]
           if isinstance(res[SIGNS[0]][k], int)}
    res["all signs"] = tot
    for key, r in res.items():
        line = (f"{key:17s} 'stop sign' {r['hit']:3d}/{r['vis']:3d}  any class {r['any']:3d}/{r['vis']:3d}  "
                f"| colour on 'stop sign' dets {r['ss_col_ok']}/{r['n_ss']} {r.get('ss_col', '')}"
                f"  on all sign dets {r['lab_col_ok']}/{r['n_lab']}")
        if base:
            line += f"  | on ref-visible frames: {r['ref_hit']}/{r['ref_vis']} (any {r['ref_any']})"
        print(line)
    # other graded objects (sanity: the new plate shouldn't hurt the chairs/ball)
    for key in ts.OBJECTS:
        if key in SIGNS:
            continue
        cls = ts.OBJECTS[key][2]
        vis = hit = 0
        for name, _ in SETS:
            meta, rows = cur[name]
            hits = {d["frame"] for d in rows if d["truth"] == key and d["cls"] == cls}
            for m in meta:
                if ts._visible(m["objects"].get(key)):
                    vis += 1
                    hit += m["frame"] in hits
        print(f"{key:17s} '{cls}' {hit}/{vis}")
    (out / "stopsign_report.json").write_text(json.dumps(res, indent=1))


def montage(out: Path, ref: Path, dest: Path, n: int = 9):
    """Before (ref) / after (out) crops of the same views: one column per view,
    sign detections drawn in, labelled with class, conf and grounded colour."""
    from PIL import Image, ImageDraw

    cur, base = _load(out), _load(ref)
    picks = []
    for key in SIGNS:   # per colour: views at increasing distance, flips first
        cands = []
        for name, _ in SETS:
            meta, rows = cur[name]
            bmeta, brows = base[name]
            bvis = {m["frame"] for m in bmeta if ts._visible(m["objects"].get(key))}
            for m in meta:
                if m["frame"] not in bvis or not ts._visible(m["objects"].get(key)):
                    continue
                hit = any(d["frame"] == m["frame"] and d["truth"] == key and d["cls"] == "stop sign" for d in rows)
                bhit = any(d["frame"] == m["frame"] and d["truth"] == key and d["cls"] == "stop sign"
                           for d in brows)
                cands.append((hit, bhit, round(m["objects"][key]["depth"], 1), name, m,
                              m["target"] == key))
        # per colour: two views the change fixed (nearest distinct distances)
        # and one it still misses (farthest), so the sheet shows failures too
        fixed, seen = [], set()
        for c in sorted((c for c in cands if c[0] and not c[1] and c[5]), key=lambda c: c[2]):
            if c[2] not in seen:
                seen.add(c[2])
                fixed.append(c)
        missed = sorted((c for c in cands if not c[0]), key=lambda c: c[2])[:1]   # nearest miss
        picks += [(key,) + c[2:5] for c in fixed[: n // 3 - len(missed)] + missed]
    cols = []
    for key, depth, name, m in picks:
        p = m["objects"][key]["box"]
        cx, cy = (p[0] + p[2]) / 2, (p[1] + p[3]) / 2
        half = max(p[2] - p[0], p[3] - p[1]) * 0.75 + 20
        box = (int(cx - half), int(cy - half), int(cx + half), int(cy + half))
        tiles = []
        for run in (base, cur):
            img = Image.open((ref if run is base else out) / name / "frames" / m["frame"]).convert("RGB")
            d = ImageDraw.Draw(img)
            dets = [r for r in run[name][1] if r["frame"] == m["frame"] and r["truth"] == key]
            for r in dets:
                d.rectangle(r["bbox"], outline=(0, 255, 255) if r["cls"] == "stop sign" else (255, 0, 255), width=2)
            tile = img.crop(box).resize((200, 200), Image.LANCZOS)
            td = ImageDraw.Draw(tile)
            ss = [r for r in dets if r["cls"] == "stop sign"]
            txt = (f"stop sign {max(r['conf'] for r in ss):.2f} {ss[0]['color_main']}" if ss
                   else (f"{dets[0]['cls']} {dets[0]['conf']:.2f}" if dets else "no detection"))
            td.rectangle((0, 182, 200, 200), fill=(0, 0, 0))
            td.text((4, 185), txt, fill=(0, 255, 0) if ss else (255, 80, 80))
            tiles.append(tile)
        head = Image.new("RGB", (200, 18), (255, 255, 255))
        ImageDraw.Draw(head).text((4, 3), f"{key.split('_')[0]} sign, {depth} m away", fill=(0, 0, 0))
        col = Image.new("RGB", (200, 418), (255, 255, 255))
        col.paste(head, (0, 0)); col.paste(tiles[0], (0, 18)); col.paste(tiles[1], (0, 218))
        cols.append(col)
    lab = Image.new("RGB", (64, 418), (255, 255, 255))
    ld = ImageDraw.Draw(lab)
    ld.text((4, 110), "BEFORE", fill=(0, 0, 0))
    ld.text((4, 310), "AFTER", fill=(0, 0, 0))
    sheet = Image.new("RGB", (64 + 204 * len(cols), 418), (255, 255, 255))
    sheet.paste(lab, (0, 0))
    for i, c in enumerate(cols):
        sheet.paste(c, (64 + 204 * i, 0))
    sheet.save(dest, optimize=True)
    print(f"montage -> {dest} ({len(cols)} views)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["run", "report", "montage"])
    ap.add_argument("--dest", type=Path, help="montage: output PNG")
    ap.add_argument("--scene", type=Path, default=Path(ts.config.SCENE_PATH))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ref", type=Path, help="report: baseline run dir for the same-frames comparison")
    a = ap.parse_args()
    if a.step == "run":
        run(a.scene, a.out)
    elif a.step == "report":
        report(a.out, a.ref)
    else:
        montage(a.out, a.ref, a.dest)


if __name__ == "__main__":
    main()
