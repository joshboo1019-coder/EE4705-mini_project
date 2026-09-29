"""
tools/visual_test_task4.py — WATCH Task 4 (Student C) run in the real sim.

Boots the REAL RealSkills + REAL RealPerception and calls
perception.navigation.goto_object() directly, so you can watch the robot
search, steer, and approach one of the objects placed in
assets/scenes/custom_scene.xml -- exactly the [SEARCH]/[DETECT]/[FOUND]/
[MISSION] behavior Task 4 is graded on, without needing Task 3's LLM
parser finished at all (navigation.py only depends on SkillsAPI /
PerceptionAPI, per core/interfaces.py).

Needs perception/perception_real.py's YOLO weights available (see
config.YOLO_MODEL) -- pass --mock-perception to fall back to the mock
detector instead, if you just want to sanity-check the search/steer/stop
LOGIC without YOLO installed (it always "finds" a fake green chair after
a few misses, so it can't verify real detection/color-grounding, only
the navigation state machine).

The browser panel (default) or native window (--native) both default to
the robot's own onboard front camera (rather than the platform's usual
third-person follow view), since what matters here is seeing what the
robot's camera sees -- the same frames perception.detect() is actually
running on -- not a spectator's-eye view of the robot from outside. Pass
--camera to pick a different one; in the browser the panel's dropdown
still lists all of them regardless, and in the native window --camera
tracking switches to the same third-person follow view.

--native opens the native MuJoCo window instead of the browser panel.
The WSL2 crash noted for this platform was specifically on-keypress
through the native window's key_callback; this script never sends it a
keypress (only navigation.goto_object() driving move()/turn()/stop()
programmatically), so that trigger shouldn't fire -- but it's unverified
on your machine, so fall back to the default browser panel if it's
unstable.

RUN (from the project root):
    python tools/visual_test_task4.py
    python tools/visual_test_task4.py --class chair --color green
    python tools/visual_test_task4.py --class "stop sign" --color red
    python tools/visual_test_task4.py --mock-perception
    python tools/visual_test_task4.py --camera tracking   # third-person instead
    python tools/visual_test_task4.py --debug-frames /tmp/color_debug  # dump crops
    python tools/visual_test_task4.py --native             # native window
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from perception import navigation
from skills.skills_real import RealSkills


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="object_class", default="chair",
                     help='COCO class name, e.g. "chair", "sports ball", '
                          '"stop sign"')
    ap.add_argument("--color", default="green",
                     help='must match a key in core.config.OBJECT_POSITIONS, '
                          'e.g. "<color>_<class>" -> "green_chair"')
    ap.add_argument("--mock-perception", action="store_true",
                     help="use perception.perception_mock.MockPerception "
                          "instead of the real YOLO detector (logic-only "
                          "check, no camera/YOLO needed)")
    ap.add_argument("--camera", default="dog_front_camera",
                     help='which camera is selected on load: '
                          '"dog_front_camera" (default, robot POV), '
                          '"tracking" (third-person follow), '
                          '"dog_rear_overhead_camera", or "dog_top_camera" '
                          '-- applies to both the browser panel and '
                          '--native')
    ap.add_argument("--debug-frames", metavar="DIR", default=None,
                     help="dump every camera frame plus each detection's "
                          "(shrunk) bbox crop as PNGs into DIR, and log "
                          "each detection's hue/sat/val stats -- use this "
                          "to see exactly which pixels color grounding is "
                          "reading when a color looks wrong (e.g. a chair "
                          "coming back \"blue\" instead of \"green\")")
    ap.add_argument("--native", action="store_true",
                     help="open the native MuJoCo window instead of the "
                          "browser panel (see module docstring)")
    args = ap.parse_args()

    print("Booting RealSkills (loads the ONNX policy + opens the MuJoCo scene)...")
    skills = RealSkills(gui=not args.native, default_camera=args.camera,
                         native_viewer=args.native)
    time.sleep(1.0)

    if args.mock_perception:
        from perception.perception_mock import MockPerception
        print("Using MockPerception -- this checks navigation.py's "
              "search/steer/approach STATE MACHINE only, not real "
              "detection or color grounding.")
        perception = MockPerception()
    else:
        from perception.perception_real import RealPerception
        perception = RealPerception(debug_dir=args.debug_frames)
        if args.debug_frames:
            print(f"[DEBUG] saving frames + bbox crops to {args.debug_frames}/")

    print(f"\ngoto_object(object_class={args.object_class!r}, "
          f"color={args.color!r}) -- watch the browser panel.\n")

    success = navigation.goto_object(args.object_class, args.color,
                                      skills, perception)

    print(f"\ngoto_object returned success={success}")
    print("Robot final pose:", skills.get_robot_pose())
    print("Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        # See visual_test_task2.py's comment on this same spot: stop()
        # alone leaves the daemon sim thread (and, with --native, the
        # GLFW window) running, and tearing the process down around
        # them is what segfaults on exit. shutdown() joins the thread
        # and closes the native viewer first.
        print("\nShutting down...")
        skills.shutdown()


if __name__ == "__main__":
    main()
