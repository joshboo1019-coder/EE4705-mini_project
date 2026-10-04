# Owner: Student C (Task 4)
# Change contributed by Student B (assist), pending review by Student C
"""Unit tests for the reactive avoidance decision (iter/avoid,
docs/iter_avoid.md). Pure functions and fakes only; no simulator."""
from types import SimpleNamespace

import pytest

from core.schema import Detection, RobotPose
from perception import navigation as nav


def test_obstacle_near_in_cone_and_nearer_than_target_triggers():
    decision = nav._avoid_decision([("green chair", 0.82, -5.0)], 3.0)
    assert decision == ("green chair", 0.82, "L")


def test_obstacle_left_of_heading_steps_right():
    assert nav._avoid_decision([("red stop sign", 0.9, 6.0)], 2.5)[2] == "R"


@pytest.mark.parametrize("obstacle, target_distance", [
    (("green chair", 1.00, 0.0), 3.0),   # not < 1.0 m
    (("green chair", 0.80, 26.0), 3.0),  # outside the +/-25 deg cone
    (("green chair", 0.80, -30.0), 3.0),
    (("green chair", 0.80, 0.0), 0.90),  # target not farther away (margin)
    (("green chair", float("inf"), 0.0), 3.0),
])
def test_no_avoidance_outside_the_rule(obstacle, target_distance):
    assert nav._avoid_decision([obstacle], target_distance) is None


def test_nearest_qualifying_obstacle_wins_and_side_is_sticky():
    obstacles = [("red stop sign", 0.95, 2.0), ("green chair", 0.70, -3.0)]
    assert nav._avoid_decision(obstacles, 3.0)[:2] == ("green chair", 0.70)
    # a side chosen earlier for the same object is kept
    assert nav._avoid_decision(obstacles, 3.0, sides={"green chair": "R"})[2] == "R"


def test_side_is_relative_to_the_target_line():
    # obstacle at -2 deg but the target is at -10 deg: obstacle is left of
    # the target line, so step right
    assert nav._avoid_decision([("green chair", 0.8, -2.0)], 3.0,
                               target_bearing_deg=-10.0)[2] == "R"


class _Skills:
    def __init__(self):
        self.moves = []

    def move(self, vx, vy, wz, duration):
        self.moves.append((vx, vy, wz, duration))

    def stop(self):
        pass

    def get_trunk_height(self):
        return 0.45


class _Perception:
    def detect_plate(self, frame, color):
        return None


def _chair_ahead_detection():
    # a chair centred in a 640x480 frame, bottom near the frame bottom:
    # estimated well under 1 m ahead
    return Detection("chair", "green", 0.8, (250.0, 200.0, 390.0, 470.0))


def test_avoid_step_logs_exact_line_and_strafes(capsys, monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    skills = _Skills()
    frame = SimpleNamespace(shape=(480, 640, 3))
    pose = RobotPose(0.0, 0.0, 0.0)
    state = {"steps": 0, "sides": {}}
    acted = nav._avoid_obstacle_ahead(
        skills, _Perception(), frame, [_chair_ahead_detection()], pose,
        "stop sign", "green", (5.0, -0.3), 5.0, state)
    assert acted
    line = capsys.readouterr().out.strip().splitlines()[-1]
    assert line.startswith("[AVOID] obj=green chair d_est=")
    label, d_est, side = line.split("obj=")[1].rsplit(" d_est=")[0], \
        float(line.split("d_est=")[1].split()[0]), line.split("side=")[1]
    assert label == "green chair" and d_est < 1.0 and side in ("L", "R")
    assert skills.moves and skills.moves[0][0] == 0.0 and skills.moves[0][1] != 0.0
    assert state["steps"] == 1 and state["sides"] == {"green chair": side}


def test_target_itself_and_far_objects_do_not_trigger(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    skills = _Skills()
    frame = SimpleNamespace(shape=(480, 640, 3))
    pose = RobotPose(0.0, 0.0, 0.0)
    state = {"steps": 0, "sides": {}}
    # the only detection is the target (same class and colour)
    assert not nav._avoid_obstacle_ahead(
        skills, _Perception(), frame, [_chair_ahead_detection()], pose,
        "chair", "green", None, 0.7, state)
    # a non-target chair, but the target is nearer than it
    assert not nav._avoid_obstacle_ahead(
        skills, _Perception(), frame, [_chair_ahead_detection()], pose,
        "sports ball", "orange", None, 0.5, state)
    assert skills.moves == []


def test_step_budget_is_bounded(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    skills = _Skills()
    frame = SimpleNamespace(shape=(480, 640, 3))
    state = {"steps": nav._AVOID_MAX_STEPS, "sides": {}}
    assert not nav._avoid_obstacle_ahead(
        skills, _Perception(), frame, [_chair_ahead_detection()],
        RobotPose(0.0, 0.0, 0.0), "stop sign", "green", None, 5.0, state)


def test_occlusion_sidestep_once_for_signs_only(monkeypatch, capsys):
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    skills = _Skills()
    state = {"steps": 0, "sides": {}}
    assert not nav._occlusion_sidestep(skills, "chair", state)
    assert nav._occlusion_sidestep(skills, "stop sign", state)
    assert not nav._occlusion_sidestep(skills, "stop sign", state)  # once per goto
    assert len(skills.moves) == 1 and skills.moves[0][1] > 0.0      # left
    assert "[SEARCH] full scan without the target" in capsys.readouterr().out
