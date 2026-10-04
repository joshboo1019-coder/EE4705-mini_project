# Owner: Student C (Task 4)
# Change contributed by Student B (assist), pending review by Student C
"""iter/chair-safety: when the target is lost and the robot's own last range
ESTIMATE is below the stop distance + CLOSE_REACQUIRE_MARGIN_M, the
re-acquire never strafes or advances: it backs off >= 0.25 m, then rotates
in place. Far from the target the original strafe sweep is unchanged."""
from types import SimpleNamespace

import pytest

from core import config
from core.schema import Detection, RobotPose
from perception import navigation


class _Skills:
    """Records every motion command; the pose follows straight moves."""

    def __init__(self):
        self.calls = []
        self.pose = RobotPose(0.0, 0.0, 0.0)

    def get_camera_frame(self):
        return SimpleNamespace(shape=(480, 640, 3))

    def stop(self):
        pass

    def move(self, vx, vy, wz, duration):
        self.calls.append(("move", vx, vy, duration))
        self.pose = RobotPose(self.pose.x + vx * duration,
                              self.pose.y + vy * duration, self.pose.yaw_deg)

    def turn(self, angle):
        self.calls.append(("turn", angle))

    def get_robot_pose(self):
        return self.pose


class _Perception:
    """Sees the target for the first `seen` frames, then never again."""

    def __init__(self, detection, seen=2):
        self.detection = detection
        self.left = seen

    def clear_target_history(self):
        pass

    def detect(self, frame, conf_threshold=None):
        if self.left > 0:
            self.left -= 1
            return [self.detection]
        return []

    def remember_target(self, frame, detection):
        pass

    def recover_target(self, frame, object_class, color, search_bbox=None):
        return None


class _Done(Exception):
    pass


def _run_until_reacquire(monkeypatch, estimated_distance):
    """goto_object on a target lost after one approach step at
    `estimated_distance`; stops at the first re-acquire action."""
    detection = Detection("chair", "red", 0.9, (300, 100, 340, 400))
    skills = _Skills()
    events = []

    def strafe(skills_, attempt, target_position):
        events.append(("strafe", attempt))
        raise _Done

    real_close = navigation._close_range_reacquire

    def close(*args, **kwargs):
        events.append(("close",))
        real_close(*args, **kwargs)
        raise _Done

    monkeypatch.setattr(navigation.time, "sleep", lambda _: None)
    monkeypatch.setattr(navigation, "_steer_to_center", lambda *a: True)
    monkeypatch.setattr(navigation, "_camera_height_above_ground", lambda *a: 0.2)
    monkeypatch.setattr(navigation, "_estimated_target_position",
                        lambda *a: (estimated_distance, 0.0))
    monkeypatch.setattr(navigation, "_estimated_planar_distance",
                        lambda *a, **k: estimated_distance)
    monkeypatch.setattr(navigation, "_ground_truth_distance", lambda *a: 9.9)
    monkeypatch.setattr(navigation, "_approach_step", lambda *a: 0.0)
    monkeypatch.setattr(navigation, "_reacquire_sweep", strafe)
    monkeypatch.setattr(navigation, "_close_range_reacquire", close)
    with pytest.raises(_Done):
        navigation.goto_object("chair", "red", skills, _Perception(detection))
    return events, skills


def test_close_range_loss_backs_off_and_never_strafes(monkeypatch):
    stop = navigation._approach_stop_m("chair")
    events, skills = _run_until_reacquire(monkeypatch, stop + 0.10)
    assert events == [("close",)]
    moves = [c for c in skills.calls if c[0] == "move"]
    # exactly one move: straight back (vx < 0, no sideways), >= 0.25 m
    assert len(moves) == 1
    _, vx, vy, duration = moves[0]
    assert vx < 0.0 and vy == 0.0
    assert abs(vx) * duration >= 0.25 - 1e-9
    # everything after the back-off is rotation in place
    assert all(c[0] == "turn" for c in skills.calls[1:])
    assert skills.pose.x == pytest.approx(-abs(vx) * duration)


def test_far_loss_keeps_the_strafe_sweep(monkeypatch):
    stop = navigation._approach_stop_m("chair")
    events, skills = _run_until_reacquire(monkeypatch, stop + 0.30)
    assert events == [("strafe", 0)]


def test_threshold_is_estimate_below_stop_plus_margin():
    stop = navigation._approach_stop_m("chair")
    margin = config.CLOSE_REACQUIRE_MARGIN_M
    assert margin == pytest.approx(0.15)
    assert navigation._too_close_to_strafe(stop + margin - 0.01, "chair")
    assert not navigation._too_close_to_strafe(stop + margin + 0.01, "chair")
    assert not navigation._too_close_to_strafe(float("inf"), "chair")
    ball_stop = navigation._approach_stop_m("sports ball")
    assert navigation._too_close_to_strafe(ball_stop + 0.1, "sports ball")


def test_close_range_reacquire_rotates_in_place_until_seen(monkeypatch, capsys):
    monkeypatch.setattr(navigation.time, "sleep", lambda _: None)
    skills = _Skills()

    class _SeenOnSecondHeading:
        def __init__(self):
            self.n = 0

        def detect(self, frame, conf_threshold=None):
            self.n += 1
            return ([Detection("chair", "red", 0.9, (0, 0, 9, 9))]
                    if self.n == 2 else [])

    new_estimate = navigation._close_range_reacquire(
        skills, _SeenOnSecondHeading(), "chair", "red", 0, (0.6, 0.0), 0.6)
    moves = [c for c in skills.calls if c[0] == "move"]
    assert len(moves) == 1 and moves[0][1] < 0.0 and moves[0][2] == 0.0
    turns = [c[1] for c in skills.calls if c[0] == "turn"]
    assert turns == [config.CLOSE_REACQUIRE_SCAN_DEG]  # 0 deg miss, +scan hit
    assert new_estimate == pytest.approx(0.6 + 0.25)
    out = capsys.readouterr().out
    assert "[REACQUIRE] target lost close-up" in out
    assert "[SEARCH]" not in out  # handout lines unchanged; only new lines


def test_close_range_reacquire_restores_heading_when_not_seen(monkeypatch):
    monkeypatch.setattr(navigation.time, "sleep", lambda _: None)
    skills = _Skills()

    class _Blind:
        def detect(self, frame, conf_threshold=None):
            return []

    navigation._close_range_reacquire(
        skills, _Blind(), "chair", "red", 1, None, 0.6)
    turns = [c[1] for c in skills.calls if c[0] == "turn"]
    scan = 2 * config.CLOSE_REACQUIRE_SCAN_DEG
    assert turns == [scan, -2 * scan, scan]
    assert sum(turns) == pytest.approx(0.0)
    assert [c for c in skills.calls if c[0] == "move"][0][2] == 0.0


def test_stuck_close_to_target_backs_off_without_strafe(monkeypatch):
    """Forward progress blocked close-up (e.g. pushing the chair): no
    strafe, the close-range back-off + rotate path runs instead."""
    detection = Detection("chair", "red", 0.9, (300, 100, 340, 400))
    skills = _Skills()
    events = []
    stop = navigation._approach_stop_m("chair")
    clock = iter(range(0, 1000, 5))

    monkeypatch.setattr(navigation.time, "sleep", lambda _: None)
    monkeypatch.setattr(navigation.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(navigation, "_steer_to_center", lambda *a: True)
    monkeypatch.setattr(navigation, "_camera_height_above_ground", lambda *a: 0.2)
    monkeypatch.setattr(navigation, "_estimated_target_position",
                        lambda *a: (stop + 0.1, 0.0))
    monkeypatch.setattr(navigation, "_estimated_planar_distance",
                        lambda *a, **k: stop + 0.1)
    monkeypatch.setattr(navigation, "_ground_truth_distance", lambda *a: 9.9)
    monkeypatch.setattr(navigation, "_approach_step", lambda *a: 0.5)

    def strafe(*a):
        events.append("strafe")
        raise _Done

    def close(*a, **k):
        events.append("close")
        raise _Done

    monkeypatch.setattr(navigation, "_reacquire_sweep", strafe)
    monkeypatch.setattr(navigation, "_close_range_reacquire", close)

    class _AlwaysSeen(_Perception):
        def detect(self, frame, conf_threshold=None):
            return [self.detection]

    with pytest.raises(_Done):
        navigation.goto_object("chair", "red", skills, _AlwaysSeen(detection))
    assert events == ["close"]
    assert not [c for c in skills.calls if c[0] == "move"]
