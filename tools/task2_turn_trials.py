# Owner: Student A (Task 2)
# Change contributed by Student B (assist), pending review by Student A
"""
tools/task2_turn_trials.py -- open-loop vs closed-loop turn trials (Task 2).

Written by Student B (assist) for Student A's Task 2 evidence, pending review
by Student A.

Measures RealSkills.turn() (Student A's closed-loop turn on true yaw) against
timed open-loop yaw-rate commands sent through RealSkills.move(0, 0, wz, t).
It does NOT change skills/skills_real.py; it only calls its public API, plus
two read-only private accessors (_get_sim_time, get_trunk_height) for logging.

Each trial starts from a settled stand and ends after the robot has settled
again, so neither the run-up of the previous trial nor the coast after the
command is lost or double-counted (see docs/report_assets/task2/README.md):

  1. stop(); wait until yaw peak-to-peak over the trailing 0.5 s of SIM time
     is < 0.2 deg (min hold 1.0 s, timeout 6 s)          -> start yaw
  2. run the command (closed: turn(angle); open: move(0, 0, wz, t))
  3. stop(); wait for the same settle criterion          -> final yaw
  4. rotation = final - start, on a continuously UNWRAPPED yaw track sampled
     at ~200 Hz, so a 180 deg turn's direction is known; heading error =
     wrap(rotation - target) in (-180, 180].

Open-loop modes (yaw-rate mapping stated explicitly, see --help):
  open_A    Student A's own --compare-turn mapping: wz = 0.6, t = 1.5 s *
            |angle| / 90 deg, i.e. it assumes 60 deg/s at wz = 0.6.
  open_cal  Same single-point / linear-in-angle method, but the rate is a
            measured one: --cal-rate deg/s (default: from a calibration
            pass, mode "cal", run first in the same process).

Ground truth is only read for logging (pose from get_robot_pose, which is
what turn() itself uses); nothing here feeds back into the open-loop command.

Run (headless, one sim process):
  QUADRUPED_MUJOCO_ROOT=/home/jiamo/EE4705/quadruped_mujoco \
    eval/run_env.sh tools/task2_turn_trials.py \
    --angles 45 90 180 --trials 6 --modes closed open_A open_cal \
    --out docs/report_assets/task2/logs/turn_trials.jsonl
"""

import argparse
import contextlib
import io
import json
import math
import os
import platform as _platform
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skills.skills_real import RealSkills  # noqa: E402

SETTLE_WINDOW_S = 0.5      # trailing sim-time window for the stillness test
SETTLE_PTP_DEG = 0.2       # yaw peak-to-peak below this -> settled
SETTLE_MIN_HOLD_S = 1.0    # always hold at least this long after stop()
SETTLE_TIMEOUT_S = 6.0

A_BASE_ANGLE, A_BASE_DURATION, A_BASE_WZ = 90.0, 1.5, 0.6   # skills_real.py --compare-turn
OPEN_WZ = 0.6
CAL_DURATION_S = 4.0       # calibration command length for mode "cal"


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


class YawTrack:
    """Samples (sim_t, unwrapped yaw, x, y) in a background thread."""

    def __init__(self, skills):
        self.s = skills
        self.buf = deque(maxlen=20000)
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._last_raw = None
        self._unwrapped = 0.0
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()

    def _run(self):
        while not self._stop.is_set():
            p = self.s.get_robot_pose()
            t = self.s._get_sim_time()
            if self._last_raw is None:
                self._unwrapped = p.yaw_deg
            else:
                self._unwrapped += wrap(p.yaw_deg - self._last_raw)
            self._last_raw = p.yaw_deg
            with self.lock:
                self.buf.append((t, self._unwrapped, p.x, p.y))
            time.sleep(0.005)

    def latest(self):
        with self.lock:
            return self.buf[-1]

    def window(self, span):
        with self.lock:
            if not self.buf:
                return []
            t_end = self.buf[-1][0]
            return [r for r in self.buf if r[0] >= t_end - span]

    def close(self):
        self._stop.set()
        self.th.join(timeout=1.0)


def wait_settled(skills, track, t_ref):
    """Blocks until yaw is still. Returns (settled, t_detect, yaw, x, y)."""
    skills.stop()
    t0 = skills._get_sim_time()
    while True:
        time.sleep(0.05)
        now = skills._get_sim_time()
        w = track.window(SETTLE_WINDOW_S)
        if now - t0 >= SETTLE_MIN_HOLD_S and len(w) > 10 and \
                w[-1][0] - w[0][0] >= SETTLE_WINDOW_S * 0.9:
            yaws = [r[1] for r in w]
            if max(yaws) - min(yaws) < SETTLE_PTP_DEG:
                last = w[-1]
                return True, now, last[1], last[2], last[3]
        if now - t0 >= SETTLE_TIMEOUT_S:
            last = track.latest()
            return False, now, last[1], last[2], last[3]


def settle_time_after(track, t_end, final_yaw):
    """Sim time from command end until yaw last left a +-SETTLE_PTP_DEG band
    around its final value (i.e. when the coast/overshoot actually ended)."""
    with track.lock:
        rows = [r for r in track.buf if r[0] >= t_end]
    last_out = t_end
    for t, y, _, _ in rows:
        if abs(y - final_yaw) > SETTLE_PTP_DEG:
            last_out = t
    return last_out - t_end


def run_trial(skills, track, mode, target, trial, cal_rate, log_f, meta):
    settled0, _, yaw0, x0, y0 = wait_settled(skills, track, None)
    t_cmd0 = skills._get_sim_time()
    w0 = time.time()
    rec = {"mode": mode, "target_deg": target, "trial": trial}
    printed = io.StringIO()
    if mode == "closed":
        with contextlib.redirect_stdout(printed):
            skills.turn(target)
        rec.update(cmd="turn", cmd_wz=None, cmd_t_s=None)
    else:
        if mode == "open_A":
            t_cmd = A_BASE_DURATION * abs(target) / A_BASE_ANGLE
            assumed = A_BASE_ANGLE / A_BASE_DURATION
        elif mode == "open_cal":
            t_cmd = abs(target) / cal_rate
            assumed = cal_rate
        elif mode == "cal":
            t_cmd = CAL_DURATION_S
            assumed = None
        else:
            raise ValueError(mode)
        wz = math.copysign(OPEN_WZ, target) if target else 0.0
        skills.move(0.0, 0.0, wz, t_cmd)
        rec.update(cmd="move", cmd_wz=wz, cmd_t_s=round(t_cmd, 4),
                   assumed_rate_deg_s=assumed)
    wall_cmd = time.time() - w0
    t_end = skills._get_sim_time()
    yaw_end_cmd = track.latest()[1]
    settled1, _, yaw1, x1, y1 = wait_settled(skills, track, t_end)
    rot = yaw1 - yaw0
    err = wrap(rot - target)
    out = printed.getvalue()
    if out:
        sys.stdout.write(out)
    m = re.search(r"final_error=(-?[\d.]+)", out)
    rec.update(
        start_settled=settled0, end_settled=settled1,
        start_yaw_deg=round(yaw0, 3), final_yaw_deg=round(yaw1, 3),
        rotation_at_cmd_end_deg=round(yaw_end_cmd - yaw0, 3),
        rotation_deg=round(rot, 3),
        heading_error_deg=round(err, 3), abs_error_deg=round(abs(err), 3),
        turn_printed_final_error_deg=float(m.group(1)) if m else None,
        cmd_sim_s=round(t_end - t_cmd0, 3),
        settle_time_s=round(settle_time_after(track, t_end, yaw1), 3),
        wall_time_s=round(time.time() - w0, 3), wall_cmd_s=round(wall_cmd, 3),
        rt_factor=round((t_end - t_cmd0) / wall_cmd, 3) if wall_cmd > 0 else None,
        start_xy=[round(x0, 3), round(y0, 3)], end_xy=[round(x1, 3), round(y1, 3)],
        trunk_z=round(skills.get_trunk_height(), 3),
        **meta,
    )
    log_f.write(json.dumps(rec) + "\n")
    log_f.flush()
    print(f"[TRIAL] {mode:8s} target={target:+6.1f} rot={rot:+8.2f} "
          f"err={err:+7.2f} settle={rec['settle_time_s']:.2f}s "
          f"wall={rec['wall_time_s']:.2f}s pos=({x1:+.2f},{y1:+.2f})")
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--angles", type=float, nargs="+", default=[45, 90, 180])
    ap.add_argument("--trials", type=int, default=6)
    ap.add_argument("--modes", nargs="+", default=["closed", "open_A", "open_cal"],
                    choices=["closed", "open_A", "open_cal"])
    ap.add_argument("--cal-rate", type=float, default=None,
                    help="deg/s at wz=0.6 for open_cal; default: measure it first "
                         f"(--cal-trials x move(0,0,+-0.6,{CAL_DURATION_S}s) in the "
                         "direction of the first --angles entry, rate = mean "
                         "settled |rotation| / duration)")
    ap.add_argument("--cal-trials", type=int, default=3)
    ap.add_argument("--out", default="docs/report_assets/task2/logs/turn_trials.jsonl")
    ap.add_argument("--run-id", default=time.strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--max-radius", type=float, default=0.8,
                    help="abort if the robot drifts further than this from spawn")
    args = ap.parse_args()

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {"run_id": args.run_id, "host": _platform.node(),
            "loadavg_start": [round(v, 2) for v in os.getloadavg()]}

    skills = RealSkills(gui=False, native_viewer=False)
    track = YawTrack(skills)
    try:
        time.sleep(1.5)
        cal_rate = args.cal_rate
        with out.open("a") as f:
            if "open_cal" in args.modes and cal_rate is None:
                rots = []
                sign = math.copysign(1.0, args.angles[0])
                meta["loadavg_1m"] = round(os.getloadavg()[0], 2)
                for k in range(1, args.cal_trials + 1):
                    r = run_trial(skills, track, "cal", sign * 90.0, k, None, f, meta)
                    rots.append(abs(r["rotation_deg"]))
                cal_rate = sum(rots) / len(rots) / CAL_DURATION_S
                print(f"[CAL] wz={OPEN_WZ} -> {cal_rate:.2f} deg/s "
                      f"(mean of {rots}, /{CAL_DURATION_S}s)")
            for angle in args.angles:
                for trial in range(1, args.trials + 1):
                    for mode in args.modes:
                        meta["loadavg_1m"] = round(os.getloadavg()[0], 2)
                        meta["cal_rate_deg_s"] = cal_rate
                        r = run_trial(skills, track, mode, angle, trial, cal_rate, f, meta)
                        if math.hypot(*r["end_xy"]) > args.max_radius:
                            print("[ABORT] robot drifted beyond --max-radius; "
                                  "rerun the remaining angles in a fresh process")
                            return 2
                        if r["trunk_z"] < 0.2:
                            print("[ABORT] trunk too low -- robot fell?")
                            return 3
    finally:
        track.close()
        skills.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
