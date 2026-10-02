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
    monkeypatch.setattr(navigation, "_approach_step", lambda *args: None)
    monkeypatch.setattr(navigation, "_reacquire_sweep", stop_at_sweep)
    monkeypatch.setattr(navigation.config, "REACQUIRE_MISSES", 3)

    with pytest.raises(_SweepReached):
        navigation.goto_object("sports ball", "orange", _Skills(), perception)

    assert sweeps == [(0, (1.0, 0.0))]
