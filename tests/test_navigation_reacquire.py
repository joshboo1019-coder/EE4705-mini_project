from types import SimpleNamespace

import numpy as np
import pytest

from core.schema import Detection, RobotPose
from perception import navigation
from perception.perception_real import RealPerception


def test_remember_target_retains_last_twenty_png_bbox_frames():
    perception = RealPerception.__new__(RealPerception)
    perception._target_history = []
    frame = np.zeros((24, 24, 3), dtype=np.uint8)

    for index in range(21):
        detection = Detection(
            "sports ball", "orange", 0.9,
            (index, index + 1, index + 2, index + 3),
        )
        perception.remember_target(frame, detection)

    history = perception._target_history
    assert len(history) == 20
    assert all(encoded.startswith(b"\x89PNG\r\n\x1a\n") for encoded, *_ in history)
    assert history[0][1] == (1, 2, 3, 4)
    assert history[-1][1] == (20, 21, 22, 23)


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


def test_goto_object_prints_typed_command_before_first_detection(capsys):
    class _DetectionStarted(Exception):
        pass

    class _TrackingPerception:
        def clear_target_history(self):
            pass

        def detect(self, frame):
            assert capsys.readouterr().out == (
                '[CMD] input="approach the green chair" '
                "action=goto_object(class=chair, color=green)\n"
            )
            raise _DetectionStarted

    with pytest.raises(_DetectionStarted):
        navigation.goto_object(
            "chair", "green", _Skills(), _TrackingPerception(),
            command_text="approach the green chair",
        )


def test_steer_to_center_accepts_target_within_wider_tolerance():
    class _TurningSkills:
        def __init__(self):
            self.turns = []

        def turn(self, angle):
            self.turns.append(angle)

    skills = _TurningSkills()
    within_tolerance = Detection("sports ball", "orange", 0.9, (185, 0, 195, 10))
    outside_tolerance = Detection("sports ball", "orange", 0.9, (186, 0, 196, 10))

    assert navigation._steer_to_center(within_tolerance, skills) is True
    assert skills.turns == []

    assert navigation._steer_to_center(outside_tolerance, skills) is False
    assert skills.turns == [-5.0]


def test_target_projection_does_not_add_fixed_range_bias():
    detection = Detection("sports ball", "orange", 0.9, (310, 200, 330, 300))
    pose = RobotPose(1.0, -2.0, 0.0)
    frame_shape = (480, 640, 3)
    camera_height = 0.6
    focal_length_px = 480 / (
        2 * navigation.math.tan(
            navigation.math.radians(navigation._CAMERA_VERTICAL_FOV_DEG) / 2
        )
    )
    image_down_angle = navigation.math.atan((300 - 240) / focal_length_px)
    ray_down_angle = (
        navigation.math.radians(navigation._CAMERA_DOWN_PITCH_DEG)
        + image_down_angle
    )
    expected_forward = (
        camera_height / navigation.math.tan(ray_down_angle)
        + navigation._CAMERA_FORWARD_OFFSET_M
    )

    target_position = navigation._estimated_target_position(
        pose, detection, frame_shape, camera_height
    )

    assert target_position == pytest.approx(
        (pose.x + expected_forward, pose.y)
    )
    assert navigation._estimated_planar_distance(
        pose, detection, frame_shape, camera_height, target_position
    ) == pytest.approx(expected_forward)


def test_reacquire_strafe_refreshes_target_position_for_range(monkeypatch):
    detection = Detection("sports ball", "orange", 0.9, (300, 200, 340, 240))
    refreshed_detection = Detection(
        "sports ball", "orange", 0.9, (360, 210, 400, 250)
    )
    initial_pose = RobotPose(0.0, 0.0, 0.0)
    post_strafe_pose = RobotPose(0.8, 0.4, 0.0)
    estimated_poses = []
    estimated_detections = []
    estimated_positions = []
    distances = []
    sleeps = []

    class _PostStrafeDistanceCalculated(Exception):
        pass

    class _MovingSkills(_Skills):
        def __init__(self):
            self.pose_calls = 0

        def get_robot_pose(self):
            self.pose_calls += 1
            return initial_pose if self.pose_calls == 1 else post_strafe_pose

    class _Perception:
        def __init__(self):
            self.calls = 0

        def clear_target_history(self):
            pass

        def detect(self, frame):
            self.calls += 1
            if self.calls in (3, 4, 5):
                return []
            if self.calls == 7:
                return [refreshed_detection]
            return [detection]

        def remember_target(self, frame, target):
            pass

    real_estimate_target_position = navigation._estimated_target_position
    real_estimated_planar_distance = navigation._estimated_planar_distance

    def estimate_target_position(pose, target, frame_shape, camera_height):
        estimated_poses.append(pose)
        estimated_detections.append(target)
        position = real_estimate_target_position(
            pose, target, frame_shape, camera_height
        )
        estimated_positions.append(position)
        return position

    def calculate_distance(pose, target, frame_shape, camera_height,
                           target_position):
        distance = real_estimated_planar_distance(
            pose, target, frame_shape, camera_height, target_position
        )
        distances.append((pose, target_position, distance))
        if target is refreshed_detection:
            raise _PostStrafeDistanceCalculated
        return distance

    monkeypatch.setattr(navigation.time, "sleep", sleeps.append)
    monkeypatch.setattr(navigation, "_steer_to_center", lambda *args: True)
    monkeypatch.setattr(navigation, "_camera_height_above_ground", lambda _: 0.6)
    monkeypatch.setattr(
        navigation, "_estimated_target_position", estimate_target_position
    )
    monkeypatch.setattr(navigation, "_estimated_planar_distance", calculate_distance)
    monkeypatch.setattr(navigation, "_ground_truth_distance", lambda *args: 2.0)
    monkeypatch.setattr(navigation, "_approach_step", lambda *args: 0.0)
    monkeypatch.setattr(navigation, "_reacquire_sweep", lambda *args: None)
    monkeypatch.setattr(navigation.config, "REACQUIRE_MISSES", 3)

    with pytest.raises(_PostStrafeDistanceCalculated):
        navigation.goto_object(
            "sports ball", "orange", _MovingSkills(), _Perception()
        )

    assert estimated_poses == [initial_pose, post_strafe_pose]
    assert estimated_detections == [detection, refreshed_detection]
    assert len(estimated_positions) == 2
    assert distances[0][0] == initial_pose
    assert distances[0][1] == estimated_positions[0]
    assert distances[0][2] == pytest.approx(
        navigation.math.hypot(
            initial_pose.x - estimated_positions[0][0],
            initial_pose.y - estimated_positions[0][1],
        )
    )
    assert distances[1][0] == post_strafe_pose
    assert distances[1][1] == estimated_positions[1]
    assert distances[1][2] == pytest.approx(
        navigation.math.hypot(
            post_strafe_pose.x - estimated_positions[1][0],
            post_strafe_pose.y - estimated_positions[1][1],
        )
    )
    assert sleeps.count(1.5) == 2


def test_obstructed_approach_backs_up_strafes_and_retries_scan(monkeypatch):
    detection = Detection("sports ball", "orange", 0.9, (300, 200, 340, 240))

    class _ForwardRetried(Exception):
        pass

    class _ObstructedSkills(_Skills):
        def __init__(self):
            self.moves = []
            self.recovered = False
            self.retried_forward_steps = 0
            self.now = 0.0

        def move(self, vx, vy, wz, duration):
            self.moves.append((vx, vy, wz, duration))
            if vx > 0.0:
                self.now += duration
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
    monkeypatch.setattr(navigation.time, "monotonic", lambda: skills.now)
    monkeypatch.setattr(navigation, "_steer_to_center", lambda *args: True)
    monkeypatch.setattr(navigation, "_camera_height_above_ground", lambda _: 0.6)
    monkeypatch.setattr(
        navigation, "_estimated_target_position", lambda *args: (1.0, 0.0)
    )
    monkeypatch.setattr(
        navigation, "_estimated_planar_distance", lambda *args, **kwargs: 2.0
    )
    monkeypatch.setattr(navigation, "_ground_truth_distance", lambda *args: 2.0)
    monkeypatch.setattr(navigation.config, "APPROACH_STUCK_TIMEOUT_S", 4.0)
    monkeypatch.setattr(navigation.config, "APPROACH_STEP_S", 0.5)

    with pytest.raises(_ForwardRetried):
        navigation.goto_object("sports ball", "orange", skills, perception)

    assert len(skills.moves) == 12
    assert all(move == (0.3, 0.0, 0.0, 0.5) for move in skills.moves[:8])
    assert skills.moves[8] == (-0.3, 0.0, 0.0, 0.5)
    assert skills.moves[9] == (0.0, 0.6, 0.0, 2.0)
    assert skills.moves[10:] == [(0.3, 0.0, 0.0, 0.5)] * 2
    assert perception.scan_count == 11


def test_recenter_time_counts_toward_four_second_recovery(monkeypatch):
    detection = Detection("sports ball", "orange", 0.9, (300, 200, 340, 240))
    now = [0.0]

    class _RecoverStarted(Exception):
        pass

    class _Skills(_Skills):
        def __init__(self):
            self.moves = []

        def move(self, vx, vy, wz, duration):
            self.moves.append((vx, vy, wz, duration))
            if vx < 0.0:
                raise _RecoverStarted

    class _Perception:
        def clear_target_history(self):
            pass

        def detect(self, frame):
            return [detection]

        def remember_target(self, frame, target):
            pass

    skills = _Skills()
    steer_calls = [0]
    attempt_started_at = [None]
    monkeypatch.setattr(navigation.time, "sleep", lambda _: None)
    monkeypatch.setattr(navigation.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(navigation, "_camera_height_above_ground", lambda _: 0.6)
    monkeypatch.setattr(
        navigation, "_estimated_target_position", lambda *args: (1.0, 0.0)
    )
    monkeypatch.setattr(
        navigation, "_estimated_planar_distance", lambda *args, **kwargs: 2.0
    )
    monkeypatch.setattr(navigation, "_ground_truth_distance", lambda *args: 2.0)
    monkeypatch.setattr(navigation.config, "APPROACH_STUCK_TIMEOUT_S", 4.0)
    monkeypatch.setattr(navigation.config, "APPROACH_STEP_S", 0.5)

    def step_forward(skills, distance):
        if attempt_started_at[0] is None:
            attempt_started_at[0] = now[0]
        now[0] += 0.5
        return 0.5

    def steer_with_recenter_time(*args):
        steer_calls[0] += 1
        if steer_calls[0] > 2:
            now[0] += 0.5
        return True

    def stop_at_strafe(*args):
        raise _RecoverStarted

    monkeypatch.setattr(navigation, "_approach_step", step_forward)
    monkeypatch.setattr(navigation, "_steer_to_center", steer_with_recenter_time)
    monkeypatch.setattr(navigation, "_reacquire_sweep", stop_at_strafe)

    with pytest.raises(_RecoverStarted):
        navigation.goto_object("sports ball", "orange", skills, _Perception())

    assert now[0] - attempt_started_at[0] <= 4.0
    assert skills.moves == [(0.3, 0.0, 0.0, 0.5), (-0.3, 0.0, 0.0, 0.5)]
