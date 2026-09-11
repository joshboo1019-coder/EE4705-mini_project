"""
tests/test_student_a.py — STUDENT A's interface/contract check.

This does not test skills_real.py's real MuJoCo behavior (that's what
`python -m skills.skills_real`'s keyboard test is for). It checks that
anything satisfying `core.interfaces.SkillsAPI` — starting with
skills/skills_mock.py's MockSkills — behaves the way Student B and
Student C's code expects. It's a concrete, runnable target to code
skills_real.RealSkills against, and it should keep passing once you swap
MockSkills for RealSkills below.

Run:
    python -m pytest -q tests/test_student_a.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.interfaces import SkillsAPI
from core.schema import RobotPose
from skills.skills_mock import MockSkills


def test_satisfies_the_interface():
    skills = MockSkills()
    assert isinstance(skills, SkillsAPI)


def test_move_and_turn_and_stop_do_not_raise():
    skills = MockSkills()
    skills.move(vx=0.8, vy=0.0, wz=0.0, duration=1.0)
    skills.turn(angle_deg=90.0)
    skills.stop()


def test_pose_and_camera_frame_have_expected_shape():
    skills = MockSkills()
    pose = skills.get_robot_pose()
    assert isinstance(pose, RobotPose)
    frame = skills.get_camera_frame()
    assert frame.ndim == 3 and frame.shape[2] == 3  # (H, W, 3) RGB


if __name__ == "__main__":
    test_satisfies_the_interface()
    test_move_and_turn_and_stop_do_not_raise()
    test_pose_and_camera_frame_have_expected_shape()
    print("Student A contract checks passed (against skills_mock.MockSkills).")
