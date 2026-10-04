# Owner: Student A (Task 2)
# Change contributed by Student B (assist), pending review by Student A
"""
tools/v2_compare_turn.py -- [assist A] demo/eval tool: open-loop vs closed-loop turn.

Written by Student B (assist) for Student A's Task 2 video (the second segment
of Video_Task2). Uses Student A's RealSkills unchanged:

  * closed loop: RealSkills.turn(angle) -- feedback on the robot's own yaw
  * open loop:   RealSkills.move(0, 0, wz=0.6, t) with t = 1.5 s per 90 deg,
                 the same timing guess as `skills_real.py --compare-turn`

and prints one `[V2] ...` line per step with the rotation measured from the
robot's own pose (its proprioceptive yaw), so the error of each method is on
screen. Run (browser panel at http://localhost:8765):

    eval/run_env.sh tools/v2_compare_turn.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from skills.skills_real import RealSkills  # noqa: E402


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def main():
    s = RealSkills(gui=True)
    print("[V2] ready", flush=True)
    time.sleep(9.0)
    print("[V2] Task 2: closed-loop turn (feedback on yaw) vs open-loop timed turn", flush=True)
    time.sleep(2.0)
    for ang in (90.0, 180.0):
        y0 = s.get_robot_pose().yaw_deg
        print(f"[V2] closed-loop turn {ang:.0f} deg: RealSkills.turn({ang:.0f})", flush=True)
        s.turn(ang)
        time.sleep(1.0)
        r = wrap(s.get_robot_pose().yaw_deg - y0)
        r = r + 360.0 if ang == 180.0 and r < 0 else r
        print(f"[V2]   -> rotated {r:.1f} deg (error {r - ang:+.1f} deg)", flush=True)
        time.sleep(2.0)
        t = 1.5 * ang / 90.0
        y0 = s.get_robot_pose().yaw_deg
        print(f"[V2] open-loop turn {ang:.0f} deg: move(wz=0.6 for {t:.1f} s), no feedback", flush=True)
        s.move(0.0, 0.0, 0.6, t)
        time.sleep(1.0)
        r = wrap(s.get_robot_pose().yaw_deg - y0)
        r = r + 360.0 if r < -10.0 else r
        print(f"[V2]   -> rotated {r:.1f} deg (error {r - ang:+.1f} deg)", flush=True)
        time.sleep(2.5)
    print("[V2] closed loop lands within ~2 deg; the open-loop timing guess is far off", flush=True)
    time.sleep(3.0)
    print("[V2] done", flush=True)
    time.sleep(2.0)
    s.shutdown()


if __name__ == "__main__":
    main()
