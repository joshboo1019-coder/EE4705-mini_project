"""
eval/scenario_mock.py — STUDENT B OWNS THIS FILE. Test doubles for the
Task 3 upgrade (programs, undo, return_home), used by tests/test_upgrade_b.py
and `eval/mock_main.py --scenario`. Not part of the robot.

skills/skills_mock.MockSkills dead-reckons along world x whatever the
heading, so "turn, then walk" never changes y and "go back to the start"
can't be checked on it. These doubles add just enough geometry:

* KinematicSkills — a MockSkills whose move() integrates the body-frame
  velocity at the current heading (SPEED_PER_UNIT m/s per unit of v,
  TURN_DPS_PER_UNIT deg/s per unit of wz) and whose turn() is exact.
* ScenarioPerception — a fake camera on that robot: it "detects" the
  objects of a small toy world (defined HERE, not config.OBJECT_POSITIONS)
  that lie inside an 80° field of view, with a bbox whose centre follows
  the bearing and whose width shrinks with range, printed like the mock's
  [DETECT] lines. It is the simulator's stand-in, so it may know where the
  toy objects are; nothing in dialogue/ ever sees those positions.
* scenario_goto — a stand-in for navigation.goto_object (Student C's) that
  uses only detections: rotate in 30° steps until the target is in view,
  turn to the bbox centre, walk the range implied by the bbox width minus
  0.8 m. Prints [MOCK goto] lines, never navigation's log lines.
"""

import math
import time
from typing import List, Optional

import numpy as np

from core.interfaces import PerceptionAPI
from core.schema import Detection, RobotPose
from skills.skills_mock import MockSkills

FRAME_W, FRAME_H = 640, 480
HFOV_DEG = 80.0
MAX_RANGE_M = 8.0
BBOX_K = 120.0     # bbox width (px) x range (m)


def _wrap(a: float) -> float:
    a = (a + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


class KinematicSkills(MockSkills):
    SPEED_PER_UNIT = 1.0       # m/s per unit of vx / vy (the real robot is ~0.96)
    TURN_DPS_PER_UNIT = 60.0

    def __init__(self, x: float = 0.0, y: float = 0.0, yaw_deg: float = 0.0,
                 sleep_scale: float = 0.0, quiet: bool = False):
        super().__init__()
        self._x, self._y, self._yaw = x, y, yaw_deg
        self.sleep_scale = sleep_scale     # real seconds slept per simulated second
        self.quiet = quiet
        self.moves, self.turns, self.stops = [], [], 0

    def move(self, vx: float, vy: float, wz: float, duration: float) -> None:
        if not self.quiet:
            print(f"[MOCK move] vx={vx} vy={vy} wz={wz} t={duration}s")
        self.moves.append((vx, vy, wz, duration))
        steps = max(1, int(round(duration / 0.05)))
        dt = duration / steps
        for _ in range(steps):
            h = math.radians(self._yaw)
            fx, fy = vx * self.SPEED_PER_UNIT, vy * self.SPEED_PER_UNIT
            self._x += (fx * math.cos(h) - fy * math.sin(h)) * dt
            self._y += (fx * math.sin(h) + fy * math.cos(h)) * dt
            self._yaw = _wrap(self._yaw + wz * self.TURN_DPS_PER_UNIT * dt)
            if self.sleep_scale:
                time.sleep(dt * self.sleep_scale)

    def turn(self, angle_deg: float) -> None:
        self.turns.append(angle_deg)
        if self.sleep_scale:
            time.sleep(abs(angle_deg) / self.TURN_DPS_PER_UNIT * self.sleep_scale)
        self._yaw = _wrap(self._yaw + angle_deg)
        print(f"[TURN] target={angle_deg:.1f} deg final_error=0.0 deg")

    def stop(self) -> None:
        self.stops += 1
        if not self.quiet:
            print("[MOCK stop]")

    def get_robot_pose(self) -> RobotPose:
        return RobotPose(x=self._x, y=self._y, yaw_deg=_wrap(self._yaw))


# The toy world (metres, world frame; the robot starts at the origin facing +x).
TOY_WORLD = [
    ("chair", "green", -2.0, 2.0),
    ("chair", "red", -2.0, -2.0),
    ("sports ball", "orange", -3.5, 0.3),
    ("stop sign", "yellow", -4.5, 2.0),
]


class ScenarioPerception(PerceptionAPI):
    def __init__(self, skills, objects=None, quiet: bool = False):
        self.skills = skills
        self.objects = list(TOY_WORLD if objects is None else objects)
        self.quiet = quiet
        self.calls = 0

    def detect(self, frame: np.ndarray,
               conf_threshold: Optional[float] = None) -> List[Detection]:
        self.calls += 1
        p = self.skills.get_robot_pose()
        out = []
        for cls, color, ox, oy in self.objects:
            dist = math.hypot(ox - p.x, oy - p.y)
            bearing = _wrap(math.degrees(math.atan2(oy - p.y, ox - p.x)) - p.yaw_deg)
            if dist > MAX_RANGE_M or abs(bearing) > HFOV_DEG / 2:
                continue
            cx = FRAME_W / 2 - bearing / (HFOV_DEG / 2) * (FRAME_W / 2)
            w = min(FRAME_W, BBOX_K / max(dist, 0.1))
            det = Detection(class_name=cls, color=color, conf=0.8,
                            bbox=(cx - w / 2, 200.0, cx + w / 2, 200.0 + w))
            out.append(det)
            if not self.quiet:
                print(f"[DETECT] class={det.class_name} color={det.color} conf={det.conf:.2f} "
                      f"bbox=[{', '.join(f'{v:.2f}' for v in det.bbox)}]")
        return out


def scenario_goto(object_class: str, color: str, skills, perception) -> bool:
    """Detection-only stand-in for navigation.goto_object (see docstring)."""
    for _ in range(13):
        dets = perception.detect(skills.get_camera_frame())
        hit = next((d for d in dets if d.class_name == object_class and d.color == color), None)
        if hit is not None:
            break
        print("[MOCK goto] target not in view, rotating 30 deg")
        skills.turn(30.0)
    else:
        print(f"[MOCK goto] {color} {object_class} not found")
        return False
    x1, _, x2, _ = hit.bbox
    bearing = ((FRAME_W / 2) - (x1 + x2) / 2) / (FRAME_W / 2) * (HFOV_DEG / 2)
    rng = BBOX_K / max(x2 - x1, 1.0)
    if abs(bearing) > 1.0:
        skills.turn(round(bearing, 1))
    walk = max(0.0, rng - 0.8)
    if walk > 0.0:
        skills.move(0.8, 0.0, 0.0, round(walk / (0.8 * KinematicSkills.SPEED_PER_UNIT), 2))
    print(f"[MOCK goto] reached {color} {object_class} (stub: range {rng:.1f} m from bbox width)")
    return True


def mock_vlm(frame, question):
    from dialogue.vlm import VLMAnswer
    return VLMAnswer("(mock VLM: no image model in the scenario run)", "mock-vlm", 0.0, 0, 0)
