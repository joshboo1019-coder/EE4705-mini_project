"""
interfaces.py — The contracts between task modules. THIS is the backbone.

Student A (Task 2) implements SkillsAPI      -> skills_real.py
Student C (Task 4) implements PerceptionAPI  -> perception_real.py

Student B (Task 3, the parser/executor/chat loop) and Student C's
navigation.py NEVER import skills_real.py or perception_real.py directly —
they only ever talk to SkillsAPI / PerceptionAPI. That is what lets you
develop and unit-test against skills_mock.py / perception_mock.py before
the real MuJoCo or YOLO code exists.

Only main.py is allowed to import the concrete *_real / *_mock classes,
because main.py is the one place that decides "wire in the real thing or
the mock" (see main.py's USE_REAL_SKILLS / USE_REAL_PERCEPTION flags).
"""

from abc import ABC, abstractmethod
from typing import List
import numpy as np
from core.schema import RobotPose, Detection


class SkillsAPI(ABC):
    """Task 2 motion + sensing skills. Implemented by Student A."""

    @abstractmethod
    def move(self, vx: float, vy: float, wz: float, duration: float) -> None:
        """Blocking timed velocity command. Must not return until `duration`
        seconds of simulated motion have elapsed. Called by the executor for
        MoveCommand and internally by navigation.py during approach."""

    @abstractmethod
    def turn(self, angle_deg: float) -> None:
        """Closed-loop turn using true yaw feedback (not open-loop timing).
        Must print '[TURN] target=<deg> final_error=<deg>' before returning."""

    @abstractmethod
    def stop(self) -> None:
        """Zero all velocity commands immediately."""

    @abstractmethod
    def get_camera_frame(self) -> np.ndarray:
        """Return the latest onboard front-camera RGB frame as (H, W, 3)
        uint8. Must be updated in the background at 10-20 Hz — do not
        render synchronously inside this call."""

    @abstractmethod
    def get_robot_pose(self) -> RobotPose:
        """Current (x, y, yaw_deg) of the robot base (trunk) in world frame."""


class PerceptionAPI(ABC):
    """Task 4 detection + color grounding. Implemented by Student C."""

    @abstractmethod
    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run YOLO + HSV color grounding on one camera frame and return
        all detections. Printing [DETECT] lines is this method's job."""
