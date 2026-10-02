from types import SimpleNamespace

import pytest

from core.schema import Detection, RobotPose
from perception import navigation


class _Skills:
    def get_camera_frame(self):
        return SimpleNamespace(shape=(480, 640, 3))

    def stop(self):
        pass

    def get_robot_pose(self):
        return RobotPose(0.0, 0.0, 0.0)


class _Perception:
    def __init__(self, detection):
        self.detection = detection
        self.detections = iter(([detection, detection] + [None] * 3))

    def clear_target_history(self):
        pass

    def detect(self, frame):
        detection = next(self.detections)
        return [detection] if detection is not None else []

    def remember_target(self, frame, detection):
        pass

    def recover_target(self, frame, object_class, color):
        return self.detection


def test_reacquire_sweep_triggers_after_three_detector_misses_even_if_recovered(
        monkeypatch):
    detection = Detection("sports ball", "orange", 0.9, (300, 200, 340, 240))
    perception = _Perception(detection)
    sweeps = []

    class _SweepReached(Exception):
        pass

    def stop_at_sweep(skills, attempt, target_position):
        sweeps.append((attempt, target_position))
        raise _SweepReached

    monkeypatch.setattr(navigation.time, "sleep", lambda _: None)
    monkeypatch.setattr(navigation, "_steer_to_center", lambda *args: True)
    monkeypatch.setattr(navigation, "_camera_height_above_ground", lambda _: 0.6)
    monkeypatch.setattr(
        navigation, "_estimated_target_position", lambda *args: (1.0, 0.0)
    )
    monkeypatch.setattr(
        navigation, "_estimated_planar_distance", lambda *args, **kwargs: 2.0
    )
    monkeypatch.setattr(navigation, "_ground_truth_distance", lambda *args: 2.0)
    monkeypatch.setattr(navigation, "_approach_step", lambda *args: 0.0)
    monkeypatch.setattr(navigation, "_reacquire_sweep", stop_at_sweep)
    monkeypatch.setattr(navigation.config, "REACQUIRE_MISSES", 3)

    with pytest.raises(_SweepReached):
        navigation.goto_object("sports ball", "orange", _Skills(), perception)

    assert sweeps == [(0, (1.0, 0.0))]


def test_obstructed_approach_backs_up_strafes_and_retries_scan(monkeypatch):
    detection = Detection("sports ball", "orange", 0.9, (300, 200, 340, 240))

    class _ForwardRetried(Exception):
        pass

    class _ObstructedSkills(_Skills):
        def __init__(self):
            self.moves = []
            self.recovered = False
            self.retried_forward_steps = 0

        def move(self, vx, vy, wz, duration):
            self.moves.append((vx, vy, wz, duration))
            if vx == 0.0 and vy != 0.0:
                self.recovered = True
            elif vx > 0.0 and self.recovered:
                self.retried_forward_steps += 1
                if self.retried_forward_steps == 2:
                    raise _ForwardRetried

    class _Perception:
        def __init__(self):
            self.scan_count = 0

        def clear_target_history(self):
            pass

        def detect(self, frame):
            self.scan_count += 1
            return [detection]

        def remember_target(self, frame, target):
            pass

    skills = _ObstructedSkills()
    perception = _Perception()
    monkeypatch.setattr(navigation.time, "sleep", lambda _: None)
    monkeypatch.setattr(navigation, "_steer_to_center", lambda *args: True)
    monkeypatch.setattr(navigation, "_camera_height_above_ground", lambda _: 0.6)
    monkeypatch.setattr(
        navigation, "_estimated_target_position", lambda *args: (1.0, 0.0)
    )
    monkeypatch.setattr(
        navigation, "_estimated_planar_distance", lambda *args, **kwargs: 2.0
    )
    monkeypatch.setattr(navigation, "_ground_truth_distance", lambda *args: 2.0)
    monkeypatch.setattr(navigation.config, "APPROACH_STUCK_TIMEOUT_S", 5.0)
    monkeypatch.setattr(navigation.config, "APPROACH_STEP_S", 0.5)

    with pytest.raises(_ForwardRetried):
        navigation.goto_object("sports ball", "orange", skills, perception)

    assert len(skills.moves) == 14
    assert all(move == (0.3, 0.0, 0.0, 0.5) for move in skills.moves[:10])
    assert skills.moves[10] == (-0.3, 0.0, 0.0, 0.5)
    assert skills.moves[11] == (0.0, 0.6, 0.0, 2.0)
    assert skills.moves[12:] == [(0.3, 0.0, 0.0, 0.5)] * 2
    assert perception.scan_count == 13
