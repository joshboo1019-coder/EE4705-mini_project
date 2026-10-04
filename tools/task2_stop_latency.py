"""
tools/task2_stop_latency.py — [B] F3 gate: e-stop latency during a 180-deg turn.
Contributed by Student B; uses Student A's RealSkills unchanged.

For each mode, from a settled stand: start a 180-deg turn in a thread, fire the
e-stop after --after s (the same two things executor.emergency_stop() does:
the abort flag that _AbortableSkills checks + skills.stop()), and measure the
time from the e-stop until the robot has stopped rotating (yaw rate below
--rate deg/s for 0.3 s of sim time). Modes:
  single   one RealSkills.turn(180) — what the executor did before F3 (a turn
           of <= 180 deg was a single, non-preemptible call)
  chunked  the F3 executor path: <= 45-deg chunks, e-stop checked between them

    QUADRUPED_MUJOCO_ROOT=... eval/run_env.sh tools/task2_stop_latency.py --trials 3
"""
import argparse, json, sys, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.task2_turn_trials import YawTrack, wait_settled  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--after", type=float, default=0.8, help="s after the turn starts")
    ap.add_argument("--rate", type=float, default=5.0, help="deg/s = stopped")
    ap.add_argument("--out", default="docs/report_assets/task2/logs/stop_latency.jsonl")
    args = ap.parse_args()
    from skills.skills_real import RealSkills
    from dialogue.executor import _AbortableSkills, ExecutionAborted
    skills = RealSkills(gui=False, native_viewer=False)
    track = YawTrack(skills)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    try:
        time.sleep(1.5)
        with out.open("a") as f:
            for trial in range(1, args.trials + 1):
                for mode in ("single", "chunked"):
                    wait_settled(skills, track, None)
                    abort = threading.Event()
                    sign = 1 if trial % 2 else -1

                    def run():
                        try:
                            if mode == "single":
                                skills.turn(180.0 * sign)
                            else:
                                _AbortableSkills(skills, abort.is_set).turn(180.0 * sign)
                        except ExecutionAborted:
                            pass
                    th = threading.Thread(target=run, daemon=True)
                    t0 = skills._get_sim_time()
                    th.start()
                    while skills._get_sim_time() < t0 + args.after:
                        time.sleep(0.005)
                    t_stop = skills._get_sim_time()
                    yaw_stop = track.latest()[1]
                    abort.set(); skills.stop()
                    stopped_at = None
                    while skills._get_sim_time() < t_stop + 8.0:
                        w = [r for r in track.window(0.3)]
                        if len(w) > 5 and w[0][0] >= t_stop and \
                                abs(w[-1][1] - w[0][1]) / max(w[-1][0] - w[0][0], 1e-3) < args.rate:
                            stopped_at = w[0][0]
                            break
                        time.sleep(0.01)
                    th.join(timeout=10)
                    lat = None if stopped_at is None else round(stopped_at - t_stop, 3)
                    extra = round(abs(track.latest()[1] - yaw_stop), 1)
                    rec = {"mode": mode, "trial": trial, "dir": sign, "after_s": args.after,
                           "latency_s": lat, "rotation_after_stop_deg": extra}
                    f.write(json.dumps(rec) + "\n"); f.flush()
                    print(f"[LATENCY] mode={mode:7s} trial={trial} latency={lat} s "
                          f"rotation_after_stop={extra} deg", flush=True)
    finally:
        track.close(); skills.shutdown()


if __name__ == "__main__":
    main()
