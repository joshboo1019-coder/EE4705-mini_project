"""
tools/task4_color_testset.py — offline colour-grounding test set for Task 4.
Written by Student B (assist Task 4) for the colour-grounding fix.

OFFLINE EVALUATION ONLY. Ground-truth object positions are used here to label
detections; nothing in the runtime path reads them.

    # 1. render dog_front_camera frames around every graded object
    MUJOCO_GL=egl python tools/task4_color_testset.py render --out DIR [--holdout]
    # 2. run YOLO (current config) on them, label each detection by overlap
    python tools/task4_color_testset.py detect --out DIR [--model yolo11s.pt]
    # 3. score perception_real's colour grounding on the saved detections
    python tools/task4_color_testset.py score --out DIR

Frames come from the real composed scene (RealSkills: same robot, lighting,
skybox, 640x480 dog_front_camera). The sim thread is stopped and the trunk
is teleported to each viewpoint with the robot in its default standing pose,
so camera intrinsics and mounting are exactly the runtime ones.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402

# key in config.OBJECT_POSITIONS -> (scene material that identifies the body, true colour, YOLO class).
# The composed scene renames bodies to mapbody_custom_scene_N, so bodies are found by material.
OBJECTS = {
    "green_chair": ("chair_green_mat", "green", "chair"),
    "red_chair": ("chair_red_mat", "red", "chair"),
    "blue_chair": ("chair_blue_mat", "blue", "chair"),
    "orange_sports ball": ("ball_orange_mat", "orange", "sports ball"),
    "red_stop sign": ("sign_red_mat", "red", "stop sign"),
    "yellow_stop sign": ("sign_yellow_mat", "yellow", "stop sign"),
    "green_stop sign": ("sign_green_mat", "green", "stop sign"),
}
BEARINGS = 8
DISTANCES = (0.8, 1.4, 2.0, 2.5)
YAW_OFFSETS = (0.0, 12.0, -12.0, 0.0)   # cycled so the object isn't always centred
TRUNK_Z = 0.32                          # standing trunk height above the ground (logged 0.32-0.33)
W, H = 640, 480


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

def _body_with_material(mujoco, model, material):
    for g in range(model.ngeom):
        mid = model.geom_matid[g]
        if mid >= 0 and (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_MATERIAL, mid) or "").endswith(material):
            return int(model.geom_bodyid[g])
    raise KeyError(material)


def _geom_corners(mujoco, model, data, g):
    t, s = model.geom_type[g], model.geom_size[g]
    if t == mujoco.mjtGeom.mjGEOM_BOX:
        half = s[:3]
    elif t == mujoco.mjtGeom.mjGEOM_SPHERE:
        half = np.array([s[0]] * 3)
    elif t in (mujoco.mjtGeom.mjGEOM_CYLINDER, mujoco.mjtGeom.mjGEOM_CAPSULE):
        half = np.array([s[0], s[0], s[1] + (s[0] if t == mujoco.mjtGeom.mjGEOM_CAPSULE else 0)])
    else:
        return np.zeros((0, 3))
    signs = np.array([[a, b, c] for a in (-1, 1) for b in (-1, 1) for c in (-1, 1)])
    local = signs * half
    return data.geom_xpos[g] + local @ data.geom_xmat[g].reshape(3, 3).T


def project_object(mujoco, model, data, cam, body):
    """Projected bbox of every geom of `body` in the camera image, unclipped,
    plus the fraction of it inside the image. None if behind the camera."""
    pts = np.concatenate([_geom_corners(mujoco, model, data, g)
                          for g in range(model.ngeom) if model.geom_bodyid[g] == body])
    R = data.cam_xmat[cam].reshape(3, 3)
    pc = (pts - data.cam_xpos[cam]) @ R
    depth = -pc[:, 2]
    if np.any(depth < 0.05):
        return None
    f = (H / 2) / math.tan(math.radians(model.cam_fovy[cam]) / 2)
    u = W / 2 + f * pc[:, 0] / depth
    v = H / 2 - f * pc[:, 1] / depth
    box = [float(u.min()), float(v.min()), float(u.max()), float(v.max())]
    area = (box[2] - box[0]) * (box[3] - box[1])
    cx1, cy1, cx2, cy2 = max(box[0], 0), max(box[1], 0), min(box[2], W), min(box[3], H)
    inside = max(0, cx2 - cx1) * max(0, cy2 - cy1)
    return dict(box=box, inside=inside / area if area > 0 else 0.0,
                visible_px=inside, depth=float(np.median(depth)))




# ---------------------------------------------------------------------------
# 1. render
# ---------------------------------------------------------------------------

def render(out: Path, holdout: bool = False):
    import mujoco
    from PIL import Image
    from skills.skills_real import RealSkills

    skills = RealSkills(gui=False)
    skills._stop_event.set()            # freeze physics; we only pose + render
    skills._sim_thread.join(timeout=5.0)
    model, data = skills._model, skills._data
    renderer = mujoco.Renderer(model, height=H, width=W)
    cam = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, "dog_front_camera")
    trunk = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    bodies = {k: _body_with_material(mujoco, model, mat) for k, (mat, _, _) in OBJECTS.items()}
    centres = {k: np.array(config.OBJECT_POSITIONS[k]) for k in OBJECTS}

    def ground_z(x, y):
        geomid = np.zeros(1, np.int32)
        d = mujoco.mj_ray(model, data, np.array([x, y, 3.0]), np.array([0, 0, -1.0]),
                          None, 1, trunk, geomid)
        return 3.0 - d if d >= 0 else 0.0

    (out / "frames").mkdir(parents=True, exist_ok=True)
    (out / "masks").mkdir(parents=True, exist_ok=True)
    meta, n = [], 0
    # held-out set: bearings shifted by half a step, distances between the tuning ones
    distances, shift = ((1.1, 1.7, 2.3), 0.5) if holdout else (DISTANCES, 0.0)
    for key in OBJECTS:
        for i in range(BEARINGS):
            for j, dist in enumerate(distances):
                a = 2 * math.pi * (i + shift) / BEARINGS + math.radians(7 * j)   # stagger rings
                x, y = centres[key] + dist * np.array([math.cos(a), math.sin(a)])
                if any(np.linalg.norm(np.array([x, y]) - c) < 0.45 for c in centres.values()):
                    continue                          # standing inside another object
                gz = ground_z(x, y)
                yaw = math.atan2(centres[key][1] - y, centres[key][0] - x) \
                    + math.radians(YAW_OFFSETS[(i + j) % len(YAW_OFFSETS)])
                data.qpos[0:3] = [x, y, gz + TRUNK_Z]
                data.qpos[3:7] = [math.cos(yaw / 2), 0, 0, math.sin(yaw / 2)]
                data.qvel[:] = 0
                mujoco.mj_forward(model, data)
                renderer.update_scene(data, camera="dog_front_camera")
                frame = renderer.render()
                renderer.enable_segmentation_rendering()
                renderer.update_scene(data, camera="dog_front_camera")
                seg = renderer.render()
                renderer.disable_segmentation_rendering()
                is_geom = seg[..., 1] == mujoco.mjtObj.mjOBJ_GEOM
                body_of_px = np.where(is_geom, model.geom_bodyid[np.clip(seg[..., 0], 0, None)], -1)
                mask = np.zeros((H, W), np.uint8)        # 0 = not a graded object, i+1 = OBJECTS[i]
                for idx, b in enumerate(bodies.values()):
                    mask[body_of_px == b] = idx + 1
                name = f"{n:04d}.png"
                Image.fromarray(frame).save(out / "frames" / name)
                Image.fromarray(mask).save(out / "masks" / name)
                proj = {k: project_object(mujoco, model, data, cam, b) for k, b in bodies.items()}
                for idx, k in enumerate(bodies):
                    if proj[k]:
                        proj[k]["seen_px"] = int(np.count_nonzero(mask == idx + 1))
                meta.append(dict(frame=name, target=key, dist=dist, bearing_deg=round(math.degrees(a), 1),
                                 pose=[round(x, 3), round(y, 3), round(gz, 3), round(math.degrees(yaw), 1)],
                                 objects={k: p for k, p in proj.items() if p}))
                n += 1
    (out / "frames.json").write_text(json.dumps(meta, indent=1))
    print(f"rendered {n} frames -> {out}")
    skills._scene.close()


# ---------------------------------------------------------------------------
# 2. detect
# ---------------------------------------------------------------------------

def _visible(p):
    """Object counts as visible: >= 60% of its projected box inside the image
    and >= 300 of its pixels actually seen (segmentation, so occlusion counts)."""
    return p is not None and p["inside"] >= 0.6 and p.get("seen_px", 0) >= 300


def label(mask, bbox, cls=None):
    """True object of a detection. First choice: an object of the detected
    YOLO class with >= 60% of its visible pixels inside the bbox (a "chair"
    box that encloses a far chair AND a nearer sign face is the chair).
    Otherwise: the graded object with the most visible pixels inside the
    bbox, if it covers >= 70% of all object pixels there and its in-box
    pixels are >= 30% of that object's visible pixels."""
    x1, y1, x2, y2 = (int(round(v)) for v in bbox)
    sub = mask[max(y1, 0):max(y2, 0), max(x1, 0):max(x2, 0)]
    counts = np.bincount(sub.ravel(), minlength=len(OBJECTS) + 1)[1:]
    if counts.sum() == 0:
        return None, 0.0, 0
    totals = np.bincount(mask.ravel(), minlength=len(OBJECTS) + 1)[1:]
    same = [i for i, (_, _, c) in enumerate(OBJECTS.values())
            if c == cls and counts[i] >= 0.6 * totals[i] and counts[i] > 0]
    if same:
        i = max(same, key=lambda j: counts[j])
        return list(OBJECTS)[i], float(counts[i] / counts.sum()), int(counts[i])
    i = int(np.argmax(counts))
    share = counts[i] / counts.sum()
    if share < 0.7 or counts[i] < 0.3 * totals[i]:
        return None, float(share), int(counts[i])
    return list(OBJECTS)[i], float(share), int(counts[i])


def detect(out: Path, model_path: str, tag: str):
    from PIL import Image
    from perception.perception_real import RealPerception
    import contextlib
    import io

    meta = json.loads((out / "frames.json").read_text())
    perc = RealPerception(model_path=model_path)
    rows, times = [], []
    for m in meta:
        frame = np.asarray(Image.open(out / "frames" / m["frame"]).convert("RGB"))
        t0 = time.perf_counter()
        with contextlib.redirect_stdout(io.StringIO()):
            dets = perc.detect(frame)
        times.append(time.perf_counter() - t0)
        mask = np.asarray(Image.open(out / "masks" / m["frame"]))
        for d in dets:
            truth, share, n_obj = label(mask, d.bbox, d.class_name)
            rows.append(dict(frame=m["frame"], target=m["target"], cls=d.class_name, conf=round(d.conf, 3),
                             bbox=[round(v, 1) for v in d.bbox], truth=truth,
                             truth_color=OBJECTS[truth][1] if truth else None,
                             truth_share=round(share, 3), obj_px=n_obj, color_main=d.color))
    (out / f"detections_{tag}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    # detection rate: frames where the object is visible -> any detection of its class overlapping it
    rate = {}
    for key, (_, _, cls) in OBJECTS.items():
        vis = [m for m in meta if _visible(m["objects"].get(key))]
        hit = [m for m in vis if any(r["frame"] == m["frame"] and r["truth"] == key and r["cls"] == cls
                                     for r in rows)]
        rate[key] = (len(hit), len(vis))
    summary = dict(model=model_path, conf=config.YOLO_CONF_THRESHOLD, imgsz=config.YOLO_IMGSZ,
                   frames=len(meta), detections=len(rows),
                   cpu_ms_median=round(1000 * float(np.median(times[1:])), 1),
                   cpu_ms_p90=round(1000 * float(np.quantile(times[1:], 0.9)), 1),
                   detection_rate={k: f"{h}/{v}" for k, (h, v) in rate.items()})
    (out / f"summary_{tag}.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


# ---------------------------------------------------------------------------
# 3. score
# ---------------------------------------------------------------------------

def score(out: Path, tag: str, field: str, recompute: bool):
    from PIL import Image
    from perception import perception_real

    rows = [json.loads(l) for l in (out / f"detections_{tag}.jsonl").open()]
    if recompute:      # re-ground with the perception_real currently on disk
        g = perception_real.RealPerception._grounded_color
        cache = {}
        for r in rows:
            if r["frame"] not in cache:
                cache = {r["frame"]: np.asarray(Image.open(out / "frames" / r["frame"]).convert("RGB"))}
            r[field] = g(_Stub(), cache[r["frame"]], tuple(r["bbox"]))
        (out / f"detections_{tag}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    lab = [r for r in rows if r["truth"]]
    for r in lab:      # two graded objects in one box (e.g. a chair box around a far chair AND a sign face)
        mask = np.asarray(Image.open(out / "masks" / r["frame"]))
        x1, y1, x2, y2 = (int(round(v)) for v in r["bbox"])
        c = np.sort(np.bincount(mask[max(y1, 0):y2, max(x1, 0):x2].ravel(), minlength=len(OBJECTS) + 1)[1:])
        r["two_objects"] = bool(c[-2] >= 0.2 * c[-1])
    print(f"{field}: {len(lab)} labelled detections ({len(rows) - len(lab)} unmatched); "
          f"{sum(r['two_objects'] for r in lab)} boxes hold two graded objects")
    for key in OBJECTS:
        rs = [r for r in lab if r["truth"] == key]
        if rs:
            ok = sum(r[field] == r["truth_color"] for r in rs)
            got = {}
            for r in rs:
                got[r[field]] = got.get(r[field], 0) + 1
            print(f"  {key:20s} {ok:3d}/{len(rs):3d}  {got}")
    colours = sorted({r["truth_color"] for r in lab})
    for c in colours:
        rs = [r for r in lab if r["truth_color"] == c]
        print(f"  colour {c:7s} {sum(r[field] == c for r in rs):3d}/{len(rs)}")
    print(f"  TOTAL {sum(r[field] == r['truth_color'] for r in lab)}/{len(lab)}")
    one = [r for r in lab if not r["two_objects"]]
    print(f"  one object in the box: {sum(r[field] == r['truth_color'] for r in one)}/{len(one)}")
    names = ["red", "orange", "yellow", "green", "blue", "purple", "pink", "unknown"]
    print("  confusion (rows = true colour, columns = grounded):")
    print("  " + " " * 8 + "".join(f"{n:>8s}" for n in names))
    for c in colours:
        print(f"  {c:8s}" + "".join(f"{sum(r['truth_color'] == c and r[field] == n for r in lab):8d}" for n in names))
    print("  unmatched detections ->", {n: sum(r[field] == n for r in rows if not r["truth"])
                                         for n in names if any(r[field] == n for r in rows if not r["truth"])})


class _Stub:
    debug_dir = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["render", "detect", "score"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default=config.YOLO_MODEL)
    ap.add_argument("--tag", default="yolo11n")
    ap.add_argument("--field", default="color_main")
    ap.add_argument("--holdout", action="store_true", help="render: the held-out viewpoints")
    ap.add_argument("--recompute", action="store_true",
                    help="re-run perception_real._grounded_color into --field")
    a = ap.parse_args()
    if a.step == "render":
        render(a.out, a.holdout)
    elif a.step == "detect":
        detect(a.out, a.model, a.tag)
    else:
        score(a.out, a.tag, a.field, a.recompute)


if __name__ == "__main__":
    main()
