"""
tools/hard_scene_check.py -- Student B (assist). Headless check of the
optional hard scene (perception/hard_scene.py, docs/hard_scene.md). No GUI,
no port: RealSkills(gui=False) only.

    QUADRUPED_MUJOCO_ROOT=... eval/run_env.sh tools/hard_scene_check.py [--out DIR]

1. Body lookup (compile only, no sim): navigation._find_target_body_id for
   every target in the hard scene, and in a "naive" variant whose second
   green chair reuses chair_green_mat (expected: LookupError).
2. Boots RealSkills(gui=False, scene_path=hard) once, dims the light, and
   calls goto_object's helpers (_camera_height_above_ground,
   _ground_truth_distance) for every target -- they must not raise.
3. Renders the onboard camera at the spawn (12 headings, the rotating search)
   and at 4 poses, runs RealPerception.detect, and saves annotated PNGs; the
   spawn heading 180 and the poses are also rendered at full light to compare,
   and at x0.3 / x0.15 light (detections only) to find where dimming breaks.
Ground truth is used only to place the robot and to label the report.
"""

import argparse
import json
import math
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from core import config  # noqa: E402
from perception import hard_scene as H  # noqa: E402

TARGETS = [("chair", "green"), ("chair", "red"), ("sports ball", "orange"),
           ("stop sign", "red"), ("stop sign", "yellow"), ("stop sign", "green"),
           ("chair", "blue")]
POSES = {   # name -> (x, y, yaw_deg, what it shows)
    "A_ball_orange_box": (-2.2, -0.5, 170.0, "ball + orange box + green chair #2"),
    "B_red_chair_red_box": (-1.0, -1.5, 215.0, "red chair + red box"),
    "C_two_green_chairs": (-1.0, 1.0, 160.0, "both green chairs, wall_north"),
    "D_behind_wall_north": (-5.8, 0.4, 51.0, "yellow stop sign from behind wall_north, diagonal"),
    "E_yellow_sign_square_on": (-4.6, -0.3, 90.0, "yellow stop sign square-on, from between the walls"),
}


def body_lookup() -> dict:
    """navigation._find_target_body_id on the composed hard scene, and on a
    naive variant (2nd chair with chair_green_mat). Compile only."""
    import skills.skills_real as sr  # puts the platform on sys.path
    import mujoco
    from runtime_control.map_manager import MapSpec, compose_scene
    from perception import navigation as nav

    out = {}
    tmp = Path(tempfile.mkdtemp(prefix="hard_scene_check_"))
    naive_xml = tmp / "custom_scene_hard_naive.xml"
    naive_xml.write_text(H.scene_path().read_text().replace(
        'material="chair_green2_mat"', 'material="chair_green_mat"'))
    for label, xml in (("hard", H.scene_path()), ("naive_same_material", naive_xml)):
        composed = compose_scene(sr.platform.DEFAULT_ROBOT_XML,
                                 {"custom_scene": MapSpec(xml)}, tmp / f"{label}.xml",
                                 robot_body_name="trunk",
                                 robot_cameras=sr.platform.ROBOT_CAMERAS)
        model = mujoco.MjModel.from_xml_path(str(composed))
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        res = {}
        for cls, color in TARGETS:
            try:
                b = nav._find_target_body_id(model, color, cls)
                res[f"{color}_{cls}"] = (None if b is None else
                                         [round(float(v), 2) for v in data.xpos[b][:2]])
            except LookupError as exc:
                res[f"{color}_{cls}"] = f"LookupError: {exc}"
        out[label] = res
    return out


def annotate(frame: np.ndarray, dets, title: str) -> Image.Image:
    img = Image.fromarray(frame).convert("RGB")
    d = ImageDraw.Draw(img)
    for det in dets:
        x1, y1, x2, y2 = det.bbox
        d.rectangle((x1, y1, x2, y2), outline=(255, 40, 40), width=3)
        label = f"{det.color} {det.class_name} {det.conf:.2f}"
        d.rectangle((x1, max(0, y1 - 14), x1 + 7 * len(label), max(14, y1)), fill=(0, 0, 0))
        d.text((x1 + 2, max(0, y1 - 13)), label, fill=(255, 255, 255))
    d.rectangle((0, 0, 8 + 7 * len(title), 16), fill=(0, 0, 0))
    d.text((4, 2), title, fill=(255, 255, 0))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "report_assets" / "hard_scene"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"layout": H.validate()}

    print("[CHECK] 1. body lookup (compile only)")
    report["body_lookup"] = body_lookup()
    print(json.dumps(report["body_lookup"], indent=1))

    from skills.skills_real import RealSkills
    from perception import navigation as nav
    from perception import scenarios
    from perception.perception_real import RealPerception

    used = H.apply_to_config()
    skills = RealSkills(gui=False, scene_path=str(H.scene_path()))
    m = skills._model
    full = (m.light_diffuse.copy(), m.light_ambient.copy(), m.light_specular.copy(),
            m.vis.headlight.diffuse.copy(), m.vis.headlight.ambient.copy(),
            m.vis.headlight.specular.copy())

    def set_light(scale):
        m.light_diffuse[:], m.light_ambient[:], m.light_specular[:] = (
            full[0] * scale, full[1] * scale, full[2] * scale)
        m.vis.headlight.diffuse[:] = full[3] * scale
        m.vis.headlight.ambient[:] = full[4] * scale
        m.vis.headlight.specular[:] = full[5] * scale
        time.sleep(0.4)   # a fresh frame (15 Hz) with the new light

    H.apply_lighting(skills)
    time.sleep(1.0)

    print("[CHECK] 2. goto_object helpers at the spawn")
    helpers = {}
    pose = skills.get_robot_pose()
    for cls, color in TARGETS:
        key = f"{color}_{cls}"
        try:
            ch = nav._camera_height_above_ground(skills, cls, color)
            gt = nav._ground_truth_distance(pose, cls, color)
            helpers[key] = {"camera_height_above_target_m": round(ch, 3),
                            "gt_distance_logged_m": round(gt, 2),
                            "gt_measures_to": used.get(key, key)}
        except Exception as exc:  # report, don't hide
            helpers[key] = {"error": repr(exc)}
    report["helpers"] = helpers
    print(json.dumps(helpers, indent=1))

    perception = RealPerception()

    def shot(name, x, y, yaw, scale=H.LIGHT_SCALE, save=True):
        scenarios.place_robot(skills, x, y, yaw, settle_s=1.6)
        if scale != H.LIGHT_SCALE:
            set_light(scale)
        frame = skills.get_camera_frame().copy()
        if scale != H.LIGHT_SCALE:
            set_light(H.LIGHT_SCALE)
        dets = perception.detect(frame)
        rec = {"pose": [x, y, yaw], "light": scale, "mean_luma": round(float(frame.mean()), 1),
               "detections": [{"class": d.class_name, "color": d.color, "conf": round(d.conf, 2),
                               "bbox": [round(v) for v in d.bbox]} for d in dets]}
        img = annotate(frame, dets, f"{name} light x{scale}")
        if save:
            img.save(out / f"{name}.png", optimize=True)
        return rec, img

    print("[CHECK] 3. spawn sweep (rotating search) at dim light")
    sweep, tiles = {}, []
    for yaw in range(0, 360, 30):
        rec, img = shot(f"spawn_yaw{yaw:03d}", 0.0, 0.0, float(yaw), save=False)
        sweep[yaw] = rec
        tiles.append(img.resize((320, 240)))
    sheet = Image.new("RGB", (4 * 320, 3 * 240))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 4) * 320, (i // 4) * 240))
    sheet.save(out / "spawn_sweep_dim.png", optimize=True)
    report["spawn_sweep_dim"] = sweep

    print("[CHECK] 4. poses, dim vs full light")
    poses = {}
    for name, (x, y, yaw, what) in {"S_spawn_yaw180": (0.0, 0.0, 180.0, "spawn facing the objects"),
                                    **POSES}.items():
        dim, dimg = shot(name + "_dim", x, y, yaw)
        bright, bimg = shot(name + "_full", x, y, yaw, scale=1.0, save=False)
        pair = Image.new("RGB", (1280, 480))
        pair.paste(bimg, (0, 0))
        pair.paste(dimg, (640, 0))
        pair.save(out / f"{name}_full_vs_dim.png", optimize=True)
        (out / f"{name}_dim.png").unlink(missing_ok=True)
        darker = {str(sc): shot(name, x, y, yaw, scale=sc, save=False)[0]
                  for sc in (0.3, 0.15)}
        poses[name] = {"what": what, "dim": dim, "full": bright, "darker": darker}
    report["poses"] = poses
    (out / "hard_scene_check.json").write_text(json.dumps(report, indent=1))
    print(f"[CHECK] report -> {out / 'hard_scene_check.json'}")
    skills.stop()


if __name__ == "__main__":
    main()
