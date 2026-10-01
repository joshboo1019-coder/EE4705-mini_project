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
from typing import List, Optional
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

    # ----------------------------------------------------------------
    # Optional extended skills (not part of the frozen core contract).
    # Default bodies raise NotImplementedError so a subclass that
    # doesn't override one fails loudly and specifically if ever called,
    # instead of an undeclared AttributeError.
    # ----------------------------------------------------------------
 
    def crouch(self) -> None:
        """Command the lower end of the implementation's stance-height
        range. Optional — see RealSkills.crouch() for the real body."""
        raise NotImplementedError("crouch() is an optional SkillsAPI "
                                   "extension; this implementation doesn't "
                                   "provide it")
 
    def stand(self) -> None:
        """Command the upper end of the implementation's stance-height
        range. Optional — see RealSkills.stand() for the real body."""
        raise NotImplementedError("stand() is an optional SkillsAPI "
                                   "extension; this implementation doesn't "
                                   "provide it")
 
    def get_trunk_height(self) -> float:
        """Diagnostic: the trunk's actual measured world-frame z. Optional
        — see RealSkills.get_trunk_height() for the real body."""
        raise NotImplementedError("get_trunk_height() is an optional "
                                   "SkillsAPI extension; this implementation "
                                   "doesn't provide it")
 
    def climb_stairs(self, target_x: float, target_y: float,
                      width_axis: Optional[str] = None,
                      width_center: Optional[float] = None,
                      width_limit: Optional[float] = None,
                      segment_len: float = 0.3, speed: float = 0.3,
                      recenter_gain: float = 0.0,
                      max_recenter_turn_deg: float = 6.0,
                      climb_height_cmd: Optional[float] = None) -> str:
        """Walk to (target_x, target_y) across a staircase, re-facing the
        target every short segment. Optional — see RealSkills.climb_stairs()
        for the real body and the real-run tuning behind its defaults."""
        raise NotImplementedError("climb_stairs() is an optional SkillsAPI "
                                   "extension; this implementation doesn't "
                                   "provide it")
 
    def cross_rough_terrain(self, target_x: float, target_y: float,
                             segment_len: float = 0.3,
                             speed: float = 0.3) -> str:
        """Walk to (target_x, target_y) across uneven/rubble terrain using
        the same segment-walk engine as climb_stairs(), without the
        width/edge guard. Optional — see RealSkills.cross_rough_terrain()."""
        raise NotImplementedError("cross_rough_terrain() is an optional "
                                   "SkillsAPI extension; this implementation "
                                   "doesn't provide it")
 
    def run_fast(self, target_x: float, target_y: float,
                 max_speed: float = 1.0,
                 accel_segments: int = 5,
                 decel_segments: int = 5,
                 ramp_segment_duration: float = 0.15,
                 cruise_segment_duration: float = 0.2,
                 heading_correction_interval: float = 1.0,
                 arrival_tolerance: float = 0.3,
                 max_duration_s: float = 30.0,
                 max_height_jump: float = 0.15,
                 stuck_dist_fraction: float = 0.25,
                 stuck_segments_before_abort: int = 3) -> str:
        """Run to (target_x, target_y) at up to max_speed with an
        accelerate/cruise/brake profile, instead of move()'s single
        constant-velocity command. Optional — see RealSkills.run_fast()
        for the real body and why it has no obstacle avoidance."""
        raise NotImplementedError("run_fast() is an optional SkillsAPI "
                                   "extension; this implementation doesn't "
                                   "provide it")


class PerceptionAPI(ABC):
    """Task 4 detection + color grounding. Implemented by Student C."""

    @abstractmethod
    def detect(self, frame: np.ndarray,
               conf_threshold: Optional[float] = None) -> List[Detection]:
        """Run YOLO + HSV color grounding on one camera frame and return
        all detections. Printing [DETECT] lines is this method's job.
        `conf_threshold` optionally overrides the default for this scan."""
