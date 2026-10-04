# Owner: Student A (Task 2)
"""
tools/capture_camera_evidence.py — STUDENT A. Standalone evidence capture
for Task 2's camera-pipeline report requirement: "save annotated frames or
a short clip as evidence."

This is intentionally independent of Task 4: it only calls
RealSkills.get_camera_frame() (the exact same call perception.detect() uses
internally), so what gets saved here is proof of the camera pipeline itself
-- the onboard dog_front_camera feed -- with no YOLO/detection dependency.
Compare to tools/visual_test_task4.py's --debug_frames, which only saves
frames as a side effect of running detection and is owned by Task 4.

Each saved PNG is annotated (frame index, elapsed time, target vs. achieved
capture rate) directly on the image, satisfying the handout's "annotated
frames" wording without needing a YOLO box to annotate with -- this is
evidence the camera pipeline itself works at the stated rate, which is what
Task 2 (not Task 4) is responsible for showing.

Rate used: defaults to core/config.py's CAMERA_HZ (the project's real,
documented rate). --hz lets you run a one-off comparison at a different
rate (e.g. 10 or 20, the handout's recommended range's endpoints) WITHOUT
editing core/config.py on disk: it overrides the shared `config.CAMERA_HZ`
attribute in memory before RealSkills is constructed, and skills_real.py
reads `config.CAMERA_HZ` fresh at __init__ time (`from core import
config`, not `from core.config import CAMERA_HZ`), so this genuinely
changes the real offscreen-render throttle for this one process only --
every other script/test that imports core.config in a separate process
still sees the real 15 Hz default.

Usage:
    python -m tools.capture_camera_evidence
    python -m tools.capture_camera_evidence --duration 8 --walk
    python -m tools.capture_camera_evidence --hz 10 --walk
    python -m tools.capture_camera_evidence --hz 20 --walk
    python -m tools.capture_camera_evidence --no-clip
    python -m tools.capture_camera_evidence --out docs/camera_evidence --gui

Output (per run, grouped by the rate actually used so --hz 10/15/20 runs
don't overwrite each other):
    <out>/<hz>hz/frame_0000.png, frame_0001.png, ...   (always)
    <out>/<hz>hz/camera_evidence.mp4                   (unless --no-clip)
"""

import argparse
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from core import config
from skills.skills_real import RealSkills

# How long to wait for the background sim thread's first real camera
# render before starting the timed capture window. Without this, frame 0
# is reliably get_camera_frame()'s documented all-zero placeholder (see
# skills_real.py's own comment on that fallback) -- a black frame that's
# misleading evidence and, before this fix, also produced a nonsense
# achieved-Hz reading on the very first sample (dividing by a near-zero
# elapsed time).
WARMUP_TIMEOUT_S = 2.0


def _annotate(frame: np.ndarray, frame_index: int, elapsed_s: float,
              target_hz: float, achieved_hz: float) -> Image.Image:
    """Draws a small readable text strip over the top of the frame. Uses
    PIL's built-in default font (no external .ttf dependency) so this runs
    anywhere Pillow is installed, same as the rest of this project."""
    img = Image.fromarray(np.asarray(frame, dtype=np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(img)
    lines = [
        f"frame {frame_index:04d}  t={elapsed_s:6.2f}s",
        f"dog_front_camera (onboard)  target={target_hz:.1f} Hz  "
        f"achieved={achieved_hz:.1f} Hz",
    ]
    pad = 4
    line_h = 14
    strip_h = pad * 2 + line_h * len(lines)
    draw.rectangle([0, 0, img.width, strip_h], fill=(0, 0, 0))
    for i, line in enumerate(lines):
        draw.text((pad, pad + i * line_h), line, fill=(0, 255, 0))
    return img


def _walk_pattern(skills: "RealSkills", total_duration: float) -> None:
    """Runs in a background thread so the robot isn't just standing still
    for the whole capture -- a slow forward walk then a turn, so the saved
    evidence shows the onboard view actually changing, not a frozen scene.
    move()/turn() are blocking per core.interfaces.SkillsAPI's contract,
    which is exactly why this needs its own thread rather than running
    inline with the capture loop below."""
    forward_s = max(0.5, total_duration * 0.5)
    tail_s = max(0.3, total_duration * 0.3)
    skills.move(vx=0.3, vy=0.0, wz=0.0, duration=forward_s)
    skills.turn(45.0)
    skills.move(vx=0.3, vy=0.0, wz=0.0, duration=tail_s)


def _wait_for_first_real_frame(skills: "RealSkills",
                                timeout_s: float = WARMUP_TIMEOUT_S) -> bool:
    """Polls get_camera_frame() until it stops returning the all-zero
    placeholder (or timeout_s elapses). Returns True if a real frame showed
    up in time, False if we gave up (capture still proceeds either way --
    a timeout just means the first frame or two may still be black, same
    as before this fix, instead of hanging the script forever)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        frame = skills.get_camera_frame()
        if np.any(frame):
            return True
        time.sleep(0.02)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture annotated onboard-camera frames (+ optional "
                     ".mp4 clip) as Task 2 report evidence for the camera "
                     "pipeline, independent of Task 4's detection code."
    )
    parser.add_argument("--duration", type=float, default=6.0,
                         help="seconds of capture (default 6.0)")
    parser.add_argument("--hz", type=float, default=None,
                         help="override the camera rate for this run only "
                              "(e.g. --hz 10 or --hz 20, to compare against "
                              "the handout's 10-20 Hz range). Defaults to "
                              "core/config.py's real CAMERA_HZ (15) if "
                              "omitted; core/config.py itself is never "
                              "edited by this flag.")

    parser.add_argument("--out", type=str, default="docs/camera_evidence",
                         help="base output directory; a <hz>hz/ subfolder "
                              "is created under it per run (default "
                              "docs/camera_evidence)")
    parser.add_argument("--walk", action="store_true",
                         help="command a slow forward walk + turn during "
                              "capture so frames show real scene motion "
                              "instead of a static standing view")
    parser.add_argument("--no-clip", action="store_true",
                         help="save PNG frames only, skip the .mp4 clip")
    parser.add_argument("--gui", action="store_true",
                         help="also open the browser control panel while "
                              "capturing (same flag as skills_real.py)")
    args = parser.parse_args()

    if args.hz is not None:
        if args.hz <= 0:
            parser.error("--hz must be > 0")
        config.CAMERA_HZ = args.hz  # in-memory only; core/config.py on disk is untouched

    effective_hz = config.CAMERA_HZ
    out_dir = Path(args.out) / f"{effective_hz:g}hz"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Booting RealSkills (headless unless --gui) for camera capture...")
    skills = RealSkills(
        gui=args.gui,
        default_camera="dog_front_camera" if args.gui else None,
    )

    got_real_frame = _wait_for_first_real_frame(skills)
    if not got_real_frame:
        print(f"[WARN] no real camera render landed within "
              f"{WARMUP_TIMEOUT_S:.1f}s warm-up; first saved frame(s) may "
              f"still be the all-zero placeholder.")

    print(f"Ready. Capturing at {effective_hz:g} Hz "
          f"{'(overridden via --hz)' if args.hz is not None else '(core/config.py CAMERA_HZ)'} "
          f"for {args.duration:.1f}s...")

    if args.walk:
        threading.Thread(
            target=_walk_pattern, args=(skills, args.duration), daemon=True
        ).start()

    period = 1.0 / effective_hz
    frames = []
    start = time.time()
    next_capture = start
    frame_index = 0
    last_capture_time = None  # for a real inter-frame Hz reading, not a
                               # cumulative frame_count/elapsed figure that
                               # spikes on the very first sample

    while time.time() - start < args.duration:
        now = time.time()
        if now >= next_capture:
            raw_frame = skills.get_camera_frame()
            elapsed = now - start
            if last_capture_time is None:
                achieved_hz = effective_hz  # first sample: nothing to
                                             # compare against yet, so
                                             # report the target rather
                                             # than a divide-by-near-zero
                                             # artifact
            else:
                achieved_hz = 1.0 / (now - last_capture_time)
            last_capture_time = now

            img = _annotate(raw_frame, frame_index, elapsed,
                             effective_hz, achieved_hz)
            img.save(out_dir / f"frame_{frame_index:04d}.png")
            frames.append(img)
            frame_index += 1
            next_capture += period
        time.sleep(0.005)

    print(f"Saved {len(frames)} annotated frames to {out_dir}/")

    if not args.no_clip and frames:
        try:
            import cv2
            clip_path = out_dir / "camera_evidence.mp4"
            w, h = frames[0].size
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(clip_path), fourcc,
                                      effective_hz, (w, h))
            for img in frames:
                writer.write(cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR))
            writer.release()
            print(f"Saved clip to {clip_path} ({effective_hz:g} fps, "
                  f"{len(frames)} frames, {len(frames) / effective_hz:.1f}s)")
        except Exception as exc:
            print(f"[WARN] could not write .mp4 clip ({exc}); PNG frames "
                  f"are still saved in {out_dir}/.")

    skills.shutdown()


if __name__ == "__main__":
    main()
