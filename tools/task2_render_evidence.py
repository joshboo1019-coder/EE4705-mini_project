# Owner: Student A (Task 2)
# Change contributed by Student B (assist), pending review by Student A
"""
tools/task2_render_evidence.py -- onboard-camera + YOLO evidence for Task 2.

Written by Student B (assist) for Student A's Task 2 evidence, pending review
by Student A.

One headless RealSkills process (gui=False, native_viewer=False), two parts:

  2.ii   "clip": teleport the robot once (sim thread paused while qpos is
         written, see _safe_teleport), let it settle, then turn slowly in
         place with move(0, 0, 0.6, T) while recording every new frame from
         RealSkills.get_camera_frame() (dog_front_camera, 15 Hz render).
         The detector then runs on each recorded frame; output is annotated
         PNGs and an H.264 mp4 (ffmpeg, libx264, yuv420p).
  2.iii  "screenshots": after the clip, physics is frozen (sim thread
         stopped, robot in its settled standing joint pose) and the trunk is
         posed at a few viewpoints facing the graded objects, trunk height =
         the settled stand height above the ray-cast ground. Each view is
         rendered from the same onboard dog_front_camera (640x480) with a
         mujoco.Renderer in this thread, then RealPerception.detect
         (yolo11n.pt, conf 0.2, imgsz 736, HSV colour grounding) runs and
         box + "class | colour | conf" are drawn on the frame. (Teleporting
         a LIVE robot repeatedly with perception.scenarios.place_robot
         segfaulted on the 2nd placement: it calls mj_forward while the sim
         thread is inside mj_step.)

Detection runs AFTER capture, on the recorded frames, so YOLO (and the GIL it
holds in pre/post-processing) cannot slow the real-time sim loop during the
motion. Same model, thresholds and colour grounding as live Task 4 use.

core.config.OBJECT_POSITIONS is read only to log which graded objects lie
inside the camera's horizontal field of view (evaluation only).

  QUADRUPED_MUJOCO_ROOT=/home/jiamo/EE4705/quadruped_mujoco \
    eval/run_env.sh tools/task2_render_evidence.py [--part all|shots|clip]
"""

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import config  # noqa: E402

OUT = ROOT / "docs" / "report_assets" / "task2"

# (name, x, y, yaw_deg) for the frozen 2.iii views. Spawn faces +x (terrain);
# the graded objects are at x < 0. Distances 1.6-3.2 m (chairs are detected
# best at 1.2-1.9 m, see docs/task4_color_grounding.md).
POSES = [
    ("overview_both_chairs", 0.6, 0.0, 180.0),
    ("green_chair_1p6m", -0.9, 0.9, 135.0),
    ("red_chair_1p6m", -0.9, -0.9, -135.0),
    ("ball_1p6m", -2.0, 0.5, -161.6),
    ("green_chair_side_1p6m", -2.0, 0.4, 90.0),
    ("yellow_stop_sign_1p8m", -3.0, 1.0, 146.3),
]
CLIP_XY = (-2.2, 0.0)   # clip: turn in place here (>= 0.9 m from every object)

BOX_RGB = {"red": (230, 40, 40), "green": (30, 170, 60), "blue": (40, 90, 230),
           "yellow": (235, 190, 0), "orange": (245, 130, 20), "purple": (150, 60, 200),
           "pink": (240, 80, 150)}


def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


F_BOX, F_HDR = _font(13), _font(13)


def annotate(frame, dets, header_lines):
    img = Image.fromarray(np.asarray(frame, dtype=np.uint8)).convert("RGB")
    d = ImageDraw.Draw(img)
    for det in dets:
        x1, y1, x2, y2 = det["bbox"]
        c = BOX_RGB.get(det["color"], (255, 255, 255))
        d.rectangle([x1, y1, x2, y2], outline=c, width=3)
        label = f"{det['class_name']} | {det['color']} | {det['conf']:.2f}"
        tw = d.textlength(label, font=F_BOX)
        ty = y1 - 18 if y1 >= 18 else y2 + 2
        d.rectangle([x1, ty, x1 + tw + 8, ty + 17], fill=c)
        d.text((x1 + 4, ty + 1), label, fill=(255, 255, 255), font=F_BOX)
    h = 6 + 17 * len(header_lines)
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(over).rectangle([0, 0, img.width, h], fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(header_lines):
        d.text((6, 4 + 17 * i), line, fill=(255, 255, 255), font=F_HDR)
    return img


def in_fov(skills, hfov_deg):
    """Graded objects inside the onboard camera's horizontal FOV (logging only)."""
    import mujoco
    m, dd = skills._model, skills._data
    cid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_CAMERA, "dog_front_camera")
    cx, cy, cz = (float(v) for v in dd.cam_xpos[cid])
    R = np.array(dd.cam_xmat[cid]).reshape(3, 3)
    fwd = -R[:, 2]                      # MuJoCo cameras look along -z
    cam_yaw = math.degrees(math.atan2(fwd[1], fwd[0]))
    vis = []
    for k, (ox, oy) in config.OBJECT_POSITIONS.items():
        b = math.degrees(math.atan2(oy - cy, ox - cx))
        rel = (b - cam_yaw + 180) % 360 - 180
        if abs(rel) <= hfov_deg / 2:
            vis.append({"object": k, "bearing_deg": round(rel, 1),
                        "dist_m": round(math.hypot(ox - cx, oy - cy), 2)})
    return {"cam_xyz": [round(cx, 3), round(cy, 3), round(cz, 3)],
            "cam_yaw_deg": round(cam_yaw, 1), "graded_in_hfov": vis}


def hfov(skills):
    import mujoco
    m = skills._model
    cid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_CAMERA, "dog_front_camera")
    fovy = float(m.cam_fovy[cid])
    return fovy, math.degrees(2 * math.atan(math.tan(math.radians(fovy) / 2) * 640 / 480))


def det_dicts(perc, frame):
    return [{"class_name": d.class_name, "color": d.color, "conf": round(d.conf, 3),
             "bbox": [round(v, 1) for v in d.bbox]} for d in perc.detect(frame)]


def _ground_z(skills, x, y):
    import mujoco
    m, d = skills._model, skills._data
    trunk = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "trunk")
    gid = np.zeros(1, np.int32)
    dist = mujoco.mj_ray(m, d, np.array([x, y, 3.0]), np.array([0, 0, -1.0]),
                         None, 1, trunk, gid)
    return 3.0 - dist if dist >= 0 else 0.0


def _set_base(skills, x, y, yaw_deg, trunk_above_ground):
    import mujoco
    d = skills._data
    half = math.radians(yaw_deg) / 2.0
    d.qpos[0:3] = (x, y, _ground_z(skills, x, y) + trunk_above_ground)
    d.qpos[3:7] = (math.cos(half), 0.0, 0.0, math.sin(half))
    d.qvel[:] = 0.0
    mujoco.mj_forward(skills._model, d)


def _pause_sim(skills):
    skills.stop()
    skills._stop_event.set()
    skills._sim_thread.join(timeout=5.0)


def _resume_sim(skills):
    import threading
    skills._stop_event.clear()
    skills._sim_thread = threading.Thread(target=skills._sim_loop, daemon=True)
    skills._sim_thread.start()


def _safe_teleport(skills, x, y, yaw_deg, settle_s=3.0):
    """Like perception.scenarios.place_robot, but with the sim thread paused
    while qpos is written, so mj_forward never races mj_step."""
    _pause_sim(skills)
    _set_base(skills, x, y, yaw_deg, 0.42 - _ground_z(skills, 0.0, 0.0))
    skills._obs_history.reset()
    skills._last_action_isaac[:] = 0.0
    _resume_sim(skills)
    time.sleep(settle_s)
    p = skills.get_robot_pose()
    print(f"[TELEPORT] x={p.x:+.2f} y={p.y:+.2f} yaw={p.yaw_deg:+.1f} "
          f"trunk_z={skills.get_trunk_height():.3f}")


def part_shots(skills, perc, outdir, fov):
    """Frozen-physics views (see module docstring)."""
    import mujoco
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "raw").mkdir(exist_ok=True)
    skills.stop()
    time.sleep(2.5)                      # settle into the standing pose first
    p0 = skills.get_robot_pose()
    stand_h = skills.get_trunk_height() - _ground_z(skills, p0.x, p0.y)
    _pause_sim(skills)
    renderer = mujoco.Renderer(skills._model, height=480, width=640)
    meta = []
    for i, (name, x, y, yaw) in enumerate(POSES, 1):
        _set_base(skills, x, y, yaw, stand_h)
        renderer.update_scene(skills._data, camera="dog_front_camera")
        frame = renderer.render().copy()
        gt = in_fov(skills, fov[1])
        dets = det_dicts(perc, frame)
        hdr = [f"dog_front_camera (onboard, z={gt['cam_xyz'][2]:.2f} m)  robot x={x:+.2f} "
               f"y={y:+.2f} yaw={yaw:+.0f}",
               f"YOLO {config.YOLO_MODEL} conf>={config.YOLO_CONF_THRESHOLD} "
               f"imgsz={config.YOLO_IMGSZ} + HSV colour  |  {len(dets)} detection(s)"]
        fn = f"yolo_{i:02d}_{name}.png"
        annotate(frame, dets, hdr).save(outdir / fn)
        Image.fromarray(frame).save(outdir / "raw" / fn)
        meta.append({"file": fn, "pose_name": name, "robot_pose": [x, y, yaw],
                     "trunk_above_ground_m": round(stand_h, 3), "detections": dets, **gt})
        print(f"[SHOT] {fn}: {[(d['color'], d['class_name'], d['conf']) for d in dets]}"
              f" | in FOV (GT): {[g['object'] for g in gt['graded_in_hfov']]}")
    renderer.close()
    return meta


def part_clip(skills, perc, outdir, fov, seconds, wz, start_yaw, keep_frames):
    outdir.mkdir(parents=True, exist_ok=True)
    _safe_teleport(skills, CLIP_XY[0], CLIP_XY[1], start_yaw)
    import threading
    frames, prev = [], None
    done = threading.Event()

    def mover():
        skills.move(0.0, 0.0, wz, seconds + 0.5)
        done.set()

    t_start = skills._get_sim_time()
    w0 = time.time()
    th = threading.Thread(target=mover, daemon=True)
    th.start()
    while not done.is_set():
        f = skills.get_camera_frame()
        if prev is None or not np.array_equal(f, prev):
            p = skills.get_robot_pose()
            frames.append((skills._get_sim_time() - t_start, p, f))
            prev = f
        time.sleep(0.01)
    th.join()
    wall = time.time() - w0
    skills.stop()
    n_keep = int(round(seconds * config.CAMERA_HZ))
    frames = frames[:n_keep]
    print(f"[CLIP] captured {len(frames)} distinct frames in {wall:.1f}s wall")

    # Detection after capture (see module docstring).
    fdir = outdir / "clip_frames"
    fdir.mkdir(exist_ok=True)
    per_frame = []
    imgs = []
    for k, (t, p, f) in enumerate(frames):
        dets = det_dicts(perc, f)
        hdr = [f"dog_front_camera (onboard)  t={t:5.2f}s  yaw={p.yaw_deg:+6.1f} deg  "
               f"turning in place, cmd wz={wz}",
               f"YOLO {config.YOLO_MODEL} conf>={config.YOLO_CONF_THRESHOLD} + HSV colour"
               f"  |  {len(dets)} detection(s)  |  frame {k:03d}"]
        img = annotate(f, dets, hdr)
        imgs.append(img)
        if k in keep_frames:
            img.save(fdir / f"frame_{k:03d}.png")
        per_frame.append({"frame": k, "t_sim_s": round(t, 3), "yaw_deg": round(p.yaw_deg, 2),
                          "x": round(p.x, 3), "y": round(p.y, 3), "detections": dets})
    mp4 = outdir / "task2_onboard_yolo_turn.mp4"
    fps = config.CAMERA_HZ
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{imgs[0].width}x{imgs[0].height}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for img in imgs:
        proc.stdin.write(np.asarray(img, dtype=np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()
    return {"file": mp4.name, "fps": fps, "n_frames": len(imgs),
            "duration_s": round(len(imgs) / fps, 2), "capture_wall_s": round(wall, 2),
            "cmd": {"vx": 0, "vy": 0, "wz": wz, "duration_s": seconds + 0.5},
            "start_yaw_cmd_deg": start_yaw,
            "yaw_first_last_deg": [per_frame[0]["yaw_deg"], per_frame[-1]["yaw_deg"]],
            "frames": per_frame}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["all", "shots", "clip"], default="all")
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--wz", type=float, default=0.6)
    ap.add_argument("--start-yaw", type=float, default=100.0)
    ap.add_argument("--keep-frames", default="0,60,112,149",
                    help="clip frame indices also saved as annotated PNGs")
    args = ap.parse_args()

    from skills.skills_real import RealSkills
    from perception.perception_real import RealPerception

    perc = RealPerception()
    skills = RealSkills(gui=False, native_viewer=False)
    run = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
           "loadavg_start": [round(v, 2) for v in os.getloadavg()],
           "yolo": {"model": config.YOLO_MODEL, "conf": config.YOLO_CONF_THRESHOLD,
                    "imgsz": config.YOLO_IMGSZ}}
    try:
        time.sleep(1.5)
        fov = hfov(skills)
        run["camera"] = {"name": "dog_front_camera", "fovy_deg": fov[0],
                         "hfov_deg": round(fov[1], 1), "px": [640, 480],
                         "render_hz": config.CAMERA_HZ}
        if args.part in ("all", "clip"):
            run["clip"] = part_clip(skills, perc, OUT / "onboard_clip", fov,
                                    args.seconds, args.wz, args.start_yaw,
                                    {int(v) for v in args.keep_frames.split(",")})
        if args.part in ("all", "shots"):
            run["shots"] = part_shots(skills, perc, OUT / "yolo_screenshots", fov)
    finally:
        skills.shutdown()
    run["loadavg_end"] = [round(v, 2) for v in os.getloadavg()]
    log = OUT / "logs" / f"render_evidence_{args.part}.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps(run, indent=1))
    print(f"[DONE] wrote {log}")


if __name__ == "__main__":
    main()
