"""
tools/video_task2_demo.py — [assist A] Video_Task2 source run.
Written by Student B (assist) for Student A's Task 2 video; uses Student A's
RealSkills unchanged. Recorded by B on the final tag (tools/record_take.py).

    eval/run_env.sh tools/video_task2_demo.py --gui [--overlay-geom 1280x720+745+2880]

Shows, with one `[V2] …` line per step: the scene and objects (browser panel,
third-person view), the onboard camera with the YOLO overlay (an OpenCV
window: boxes, class, colour, confidence) and `[DETECT]` lines, timed moves
(forward / backward / lateral left / right) and closed-loop turns left and
right incl. 90 and 180 deg with A's `[TURN] … final_error=…` lines.
The robot spawns at the origin facing +x; the objects stand behind it
(x < 0) and the terrain track starts at x ≈ 1.5 m ahead, so moves stay short.
"""

import argparse
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WIN = "onboard camera + YOLO"
COLORS = {"red": (60, 60, 230), "green": (60, 200, 60), "blue": (230, 120, 40),
          "orange": (40, 150, 255), "yellow": (40, 220, 230)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gui", action="store_true")
    ap.add_argument("--overlay-geom", default="960x720+0+720",
                    help="WxH+X+Y of the overlay window on the X screen")
    args = ap.parse_args()
    import cv2
    from skills.skills_real import RealSkills
    from perception.perception_real import RealPerception

    w, h, x, y = map(int, re.fullmatch(r"(\d+)x(\d+)\+(\d+)\+(\d+)", args.overlay_geom).groups())
    skills = RealSkills(gui=args.gui)
    perception = RealPerception()
    state = {"done": False, "frame": None, "dets": [], "detect": True}
    lock = threading.Lock()

    def detector():
        last_print = 0.0
        while not state["done"]:
            frame = skills.get_camera_frame()
            if frame is None:
                time.sleep(0.1)
                continue
            if state["detect"] and time.time() - last_print > 1.0:
                dets = perception.detect(frame)          # prints [DETECT] lines (~1 Hz)
                last_print = time.time()
            else:
                import contextlib, io
                with contextlib.redirect_stdout(io.StringIO()):
                    dets = perception.detect(frame)
            with lock:
                state["frame"], state["dets"] = frame, dets
            time.sleep(0.15)

    def step(text, fn, pause=1.0):
        print(f"[V2] {text}", flush=True)
        fn()
        time.sleep(pause)

    def choreography():
        try:
            time.sleep(2.0)
            print("[V2] ready", flush=True)
            time.sleep(6.0)
            print("[V2] scene: the objects stand behind the robot (x < 0); onboard camera + YOLO bottom-left",
                  flush=True)
            time.sleep(3.0)
            step("timed move: forward 1.5 s at vx=0.8", lambda: skills.move(0.8, 0.0, 0.0, 1.5))
            step("timed move: backward 1.5 s at vx=-0.8", lambda: skills.move(-0.8, 0.0, 0.0, 1.5))
            step("timed move: lateral left 1.5 s at vy=+0.8", lambda: skills.move(0.0, 0.8, 0.0, 1.5))
            step("timed move: lateral right 1.5 s at vy=-0.8", lambda: skills.move(0.0, -0.8, 0.0, 1.5))
            step("closed-loop turn left 90 deg", lambda: skills.turn(90.0))
            step("closed-loop turn right 90 deg", lambda: skills.turn(-90.0))
            step("closed-loop turn 180 deg -> facing the objects", lambda: skills.turn(180.0), pause=2.0)
            print("[V2] onboard camera: YOLO detects the scene objects (boxes + [DETECT] lines)", flush=True)
            time.sleep(10.0)
            step("closed-loop turn -180 deg (right) -> back to the start heading", lambda: skills.turn(-180.0),
                 pause=2.0)
            p = skills.get_robot_pose()
            print(f"[V2] final pose x={p.x:.2f} y={p.y:.2f} yaw={p.yaw_deg:.1f} deg", flush=True)
            time.sleep(2.0)
            print("[V2] done", flush=True)
        finally:
            state["done"] = True

    threading.Thread(target=detector, daemon=True).start()
    threading.Thread(target=choreography, daemon=True).start()
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN, w, h)
    cv2.moveWindow(WIN, x, y)
    try:
        while True:
            with lock:
                frame, dets = state["frame"], list(state["dets"])
            if frame is not None:
                img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR).copy()
                for d in dets:
                    x1, y1, x2, y2 = map(int, d.bbox)
                    c = COLORS.get(d.color, (220, 220, 220))
                    cv2.rectangle(img, (x1, y1), (x2, y2), c, 2)
                    cv2.putText(img, f"{d.color} {d.class_name} {d.conf:.2f}", (x1, max(14, y1 - 5)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 2)
                cv2.putText(img, "onboard camera (dog_front_camera) + YOLO", (8, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
                cv2.imshow(WIN, cv2.resize(img, (w, h)))
            if cv2.waitKey(60) == 27:
                break
            if state["done"]:
                # keep the last frame on screen until the recorder stops us
                pass
    except KeyboardInterrupt:
        pass
    finally:
        state["done"] = True
        cv2.destroyAllWindows()
        skills.shutdown()


if __name__ == "__main__":
    main()
