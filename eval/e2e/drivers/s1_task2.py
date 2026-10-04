# Owner: Student B (Task 3 + bonuses)
"""
eval/e2e/drivers/s1_task2.py — Student B. e2e suite S1 (Task 2 skills).

    eval/run_env.sh eval/e2e/drivers/s1_task2.py --mode closed|open|move [--gui]

closed: RealSkills.turn(a) (A's closed-loop turn) for a in 45/90/180, 3 trials each.
open:   timed yaw-rate commands aimed at the same angles, using A's own
        open-loop mapping from `skills_real --compare-turn`
        (90 deg = 1.5 s at wz=0.6, scaled linearly with the angle).
move:   turn left 90 (closed loop, onto the clear strip at x~0), then one
        timed 3 s move at vx=0.8; reports the distance travelled.
Each result is printed as one `[S1] ...` line (measured from get_robot_pose,
which is what A's turn() itself uses). Ends with `[S1] done`.
"""

import argparse
import math
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

ANGLES = (45.0, 90.0, 180.0)
TRIALS = 3
BASE_ANGLE, BASE_DURATION, BASE_WZ = 90.0, 1.5, 0.6   # skills_real --compare-turn


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("closed", "open", "move"), required=True)
    ap.add_argument("--gui", action="store_true")
    args = ap.parse_args()

    from skills.skills_real import RealSkills
    skills = RealSkills(gui=args.gui)
    if os.environ.get("E2E_TRACE_FILE"):
        from eval.e2e.trace import start_trace
        start_trace(skills, os.environ["E2E_TRACE_FILE"])
    time.sleep(2.0)
    print("[S1] ready", flush=True)
    time.sleep(3.0)   # recorder + panel settle

    try:
        if args.mode in ("closed", "open"):
            for angle in ANGLES:
                for trial in range(1, TRIALS + 1):
                    yaw0 = skills.get_robot_pose().yaw_deg
                    t0 = time.time()
                    if args.mode == "closed":
                        skills.turn(angle)
                        extra = ""
                    else:
                        dur = BASE_DURATION * angle / BASE_ANGLE
                        skills.move(0.0, 0.0, BASE_WZ, dur)
                        time.sleep(0.5)          # let the spin settle before measuring
                        extra = f" wz={BASE_WZ} duration={dur:.2f} s"
                    wall = time.time() - t0
                    got = wrap(skills.get_robot_pose().yaw_deg - yaw0)
                    if angle >= 179.0 and got < 0:
                        got += 360.0
                    print(f"[S1] mode={args.mode} target={angle:.0f} trial={trial} "
                          f"achieved={got:.1f} error={got - angle:+.1f} deg "
                          f"t={wall:.1f} s{extra}", flush=True)
                    time.sleep(1.0)
        else:
            skills.turn(90.0)
            time.sleep(0.5)
            p0 = skills.get_robot_pose()
            t0 = time.time()
            skills.move(0.8, 0.0, 0.0, 3.0)
            time.sleep(0.5)
            p1 = skills.get_robot_pose()
            d = math.hypot(p1.x - p0.x, p1.y - p0.y)
            print(f"[S1] mode=move vx=0.8 duration=3.0 s distance={d:.2f} m "
                  f"heading_change={wrap(p1.yaw_deg - p0.yaw_deg):+.1f} deg "
                  f"t={time.time() - t0:.1f} s", flush=True)
        print("[S1] done", flush=True)
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        skills.shutdown()


if __name__ == "__main__":
    main()
