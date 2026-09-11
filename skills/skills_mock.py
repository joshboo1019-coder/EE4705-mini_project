"""
skills_mock.py — Fake SkillsAPI for offline development/testing.

Student B: use this to run llm_parser.py + executor.py end-to-end before
Student A's simulation works. `python tests/test_parser_with_mock.py`.

Student C: use this to unit-test navigation.py's search/steer/approach
logic without needing MuJoCo running at all.

NOT SUBMITTED AS THE FINAL SYSTEM — it's a dev/test double for skills_real.py.
"""

import time
import numpy as np
from core.interfaces import SkillsAPI
from core.schema import RobotPose


class MockSkills(SkillsAPI):
    def __init__(self):
        self._x, self._y, self._yaw = 0.0, 0.0, 0.0

    def move(self, vx: float, vy: float, wz: float, duration: float) -> None:
        print(f"[MOCK move] vx={vx} vy={vy} wz={wz} t={duration}s")
        # crude dead-reckoning so distances/poses move somewhat sensibly
        self._x += vx * duration * 0.3
        self._y += vy * duration * 0.3
        time.sleep(min(duration, 0.2))  # don't actually block tests for real time

    def turn(self, angle_deg: float) -> None:
        self._yaw = (self._yaw + angle_deg) % 360
        final_error = 1.5  # pretend the closed loop settles with small error
        print(f"[TURN] target={angle_deg:.1f} deg final_error={final_error:.1f} deg")

    def stop(self) -> None:
        print("[MOCK stop]")

    def get_camera_frame(self) -> np.ndarray:
        return np.zeros((240, 320, 3), dtype=np.uint8)

    def get_robot_pose(self) -> RobotPose:
        return RobotPose(x=self._x, y=self._y, yaw_deg=self._yaw)
