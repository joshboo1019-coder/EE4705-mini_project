# Owner: Student C (Task 4)
# Change contributed by Student B (assist), pending review by Student C
from types import SimpleNamespace

import numpy as np
import pytest

from core import config
from core.schema import Detection, RobotPose
from perception import navigation, perception_real
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

    # The limit is tuned by Student C (_TARGET_HISTORY_LIMIT, 8 at the time
    # of writing); the test name predates that tuning.
    limit = perception_real._TARGET_HISTORY_LIMIT
    oldest = 21 - limit
    history = perception._target_history
    assert len(history) == limit
    assert all(encoded.startswith(b"\x89PNG\r\n\x1a\n") for encoded, *_ in history)
    assert history[0][1] == (oldest, oldest + 1, oldest + 2, oldest + 3)
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
    monkeypatch.setattr(
        navigation, "_camera_height_above_ground", lambda *_: 0.6
    )
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
    # Default frame_width=320 -> center x=160; bbox is 10 px wide.
    tolerance = config.CENTER_TOLERANCE_PX
    within_tolerance = Detection(
        "sports ball", "orange", 0.9,
        (155 + tolerance, 0, 165 + tolerance, 10),
    )
    outside_tolerance = Detection(
        "sports ball", "orange", 0.9,
        (156 + tolerance, 0, 166 + tolerance, 10),
    )

    assert navigation._steer_to_center(within_tolerance, skills) is True
    assert skills.turns == []

    assert navigation._steer_to_center(outside_tolerance, skills) is False
    assert skills.turns == [-5.0]


def _bbox_for(center_z, distance, camera_z, class_height, frame_h=480):
    """A bbox of a target whose centre is at center_z, `distance` m ahead of
    the camera (ideal pinhole, the module's own camera constants)."""
    import math
    f = frame_h / (2 * math.tan(math.radians(navigation._CAMERA_VERTICAL_FOV_DEG) / 2))
    ray = math.atan((camera_z - center_z) / distance)
    cy = frame_h / 2 + f * math.tan(ray - math.radians(navigation._CAMERA_DOWN_PITCH_DEG))
    h = f * class_height / distance
    return (300.0, cy - h / 2, 340.0, cy + h / 2)


def test_camera_height_never_reads_the_simulator():
    """assist/no-gt-height: the target's height is not ground truth. A skills
    object whose simulator state explodes on access must still work."""
    class _NoSimSkills(_Skills):
        @property
        def _model(self):
            raise AssertionError("navigation read skills._model")

        @property
        def _data(self):
            raise AssertionError("navigation read skills._data")

        def get_trunk_height(self):
            return 0.33

    camera_z = 0.33 + navigation._CAMERA_HEIGHT_ABOVE_TRUNK_M
    for cls, nominal in navigation._NOMINAL_CENTER_HEIGHTS_M.items():
        assert navigation._camera_height_above_ground(
            _NoSimSkills(), cls, "blue") == pytest.approx(camera_z - nominal)


def test_floor_target_uses_the_nominal_height():
    camera_z = 0.49
    bbox = _bbox_for(0.44, 2.5, camera_z, navigation._TARGET_HEIGHTS_M["chair"])
    det = Detection("chair", "green", 0.9, bbox)
    assert navigation._target_center_height("chair", det, (480, 640, 3), camera_z) == 0.44


def test_elevated_target_height_is_estimated_from_the_bbox():
    """The blue chair on the stairs: centre ~0.84 m (0.40 m up)."""
    camera_z = 0.49
    for distance in (1.5, 2.5, 3.5):
        bbox = _bbox_for(0.84, distance, camera_z, navigation._TARGET_HEIGHTS_M["chair"])
        det = Detection("chair", "blue", 0.9, bbox)
        z = navigation._target_center_height("chair", det, (480, 640, 3), camera_z)
        assert z == pytest.approx(0.84, abs=1e-6)


def test_cut_or_tiny_bbox_falls_back_to_the_nominal_height():
    camera_z = 0.49
    cut = Detection("chair", "blue", 0.9, (300.0, 0.0, 340.0, 200.0))       # touches the top edge
    tiny = Detection("chair", "blue", 0.9, (300.0, 100.0, 310.0, 110.0))    # 10 px tall
    for det in (cut, tiny):
        assert navigation._target_center_height("chair", det, (480, 640, 3), camera_z) == 0.44


def test_stop_signs_keep_the_nominal_height():
    camera_z = 0.49
    bbox = _bbox_for(0.85, 2.0, camera_z, navigation._TARGET_HEIGHTS_M["stop sign"])
    det = Detection("stop sign", "red", 0.9, bbox)
    assert navigation._target_center_height("stop sign", det, (480, 640, 3), camera_z) == 0.50


def test_target_projection_uses_bbox_center_without_fixed_range_bias():
    detection = Detection("sports ball", "orange", 0.9, (310, 200, 330, 300))
    pose = RobotPose(1.0, -2.0, 0.0)
    frame_shape = (480, 640, 3)
    camera_height = 0.6
    focal_length_px = 480 / (
        2 * navigation.math.tan(
            navigation.math.radians(navigation._CAMERA_VERTICAL_FOV_DEG) / 2
        )
    )
    bbox_center_y = (200 + 300) / 2
    image_down_angle = navigation.math.atan(
        (bbox_center_y - 240) / focal_length_px
    )
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


@pytest.mark.parametrize(
    ("object_class", "target_height"),
    # iter/stopsign-plate: "stop sign" uses the plate range model
    # (tests/test_stopsign_plate.py::test_sign_range_model)
    [("chair", 0.88), ("sports ball", 0.22)],
)
def test_target_projection_uses_bbox_size_at_camera_height(
        object_class, target_height):
    pose = RobotPose(0.0, 0.0, 0.0)
    frame_shape = (480, 640, 3)
    bbox_height = 100.0
    detection = Detection(
        object_class, "green", 0.9,
        (310, 190, 330, 190 + bbox_height),
    )
    focal_length_px = 480 / (
        2 * navigation.math.tan(
            navigation.math.radians(navigation._CAMERA_VERTICAL_FOV_DEG) / 2
        )
    )
    expected_forward = (
        focal_length_px * target_height / bbox_height
        + navigation._CAMERA_FORWARD_OFFSET_M
    )

    target_position = navigation._estimated_target_position(
        pose, detection, frame_shape, camera_height=0.0
    )

    assert target_position == pytest.approx((expected_forward, 0.0))
    assert navigation._estimated_planar_distance(
        pose, detection, frame_shape, camera_height=0.0,
        target_position=target_position,
    ) == pytest.approx(expected_forward)


def test_target_projection_uses_bbox_size_for_near_horizontal_ray():
    pose = RobotPose(0.0, 0.0, 0.0)
    frame_shape = (480, 640, 3)
    camera_height = 0.17
    bbox_height = 50.0
    focal_length_px = 480 / (
        2 * navigation.math.tan(
            navigation.math.radians(navigation._CAMERA_VERTICAL_FOV_DEG) / 2
        )
    )
    bbox_center_y = 240 - focal_length_px * navigation.math.tan(
        navigation.math.radians(navigation._CAMERA_DOWN_PITCH_DEG)
    )
    detection = Detection(
        "sports ball", "orange", 0.9,
        (310, bbox_center_y - bbox_height / 2,
         330, bbox_center_y + bbox_height / 2),
    )
    expected_forward = (
        focal_length_px * 0.22 / bbox_height
        + navigation._CAMERA_FORWARD_OFFSET_M
    )

    target_position = navigation._estimated_target_position(
        pose, detection, frame_shape, camera_height
    )

    assert target_position == pytest.approx((expected_forward, 0.0))


def test_target_projection_handles_target_center_above_camera():
    pose = RobotPose(0.0, 0.0, 0.0)
    frame_shape = (480, 640, 3)
    target_center_z = 0.84
    camera_z = 0.50 + navigation._CAMERA_HEIGHT_ABOVE_TRUNK_M
    camera_height = camera_z - target_center_z
    # Rays within _NEAR_HORIZONTAL_RAY_ANGLE_DEG are ranged by bbox size
    # (0b438c0); at 3.0 m this ray was only ~3.4 deg, so use 1.0 m to keep
    # the signed vertical-angle path under test.
    expected_camera_forward = 1.0
    ray_down_angle = navigation.math.atan(
        camera_height / expected_camera_forward
    )
    assert abs(ray_down_angle) > navigation.math.radians(
        navigation._NEAR_HORIZONTAL_RAY_ANGLE_DEG
    )
    focal_length_px = 480 / (
        2 * navigation.math.tan(
            navigation.math.radians(navigation._CAMERA_VERTICAL_FOV_DEG) / 2
        )
    )
    image_down_angle = (
        ray_down_angle
        - navigation.math.radians(navigation._CAMERA_DOWN_PITCH_DEG)
    )
    bbox_center_y = 240 + focal_length_px * navigation.math.tan(
        image_down_angle
    )
    detection = Detection(
        "chair", "blue", 0.9,
        (310, bbox_center_y - 20, 330, bbox_center_y + 20),
    )

    target_position = navigation._estimated_target_position(
        pose, detection, frame_shape, camera_height
    )

    assert target_position == pytest.approx(
        (expected_camera_forward + navigation._CAMERA_FORWARD_OFFSET_M, 0.0)
    )
    assert navigation._estimated_planar_distance(
        pose, detection, frame_shape, camera_height, target_position
    ) == pytest.approx(
        expected_camera_forward + navigation._CAMERA_FORWARD_OFFSET_M
    )


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
    monkeypatch.setattr(
        navigation, "_camera_height_above_ground", lambda *_: 0.6
    )
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
    monkeypatch.setattr(
        navigation, "_camera_height_above_ground", lambda *_: 0.6
    )
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
    assert skills.moves[9] == (
        0.0, config.REACQUIRE_STRAFE_VY, 0.0, config.REACQUIRE_STRAFE_S
    )
    assert skills.moves[10:] == [(0.3, 0.0, 0.0, 0.5)] * 2
    # 8 approach + 1 initial-center + 1 post-strafe settle re-detect + 2 retry
    assert perception.scan_count == 12


@pytest.mark.xfail(
    reason="expects a (0.3, 0, 0, 0.5) forward move but its own "
           "_approach_step fake never calls skills.move; intent needs Student C",
    strict=False,
)
def test_recenter_time_counts_toward_four_second_recovery(monkeypatch):
    detection = Detection("sports ball", "orange", 0.9, (300, 200, 340, 240))
    now = [0.0]

    class _RecoverStarted(Exception):
        pass

    class _RecoverSkills(_Skills):
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

    skills = _RecoverSkills()
    steer_calls = [0]
    attempt_started_at = [None]
    monkeypatch.setattr(navigation.time, "sleep", lambda _: None)
    monkeypatch.setattr(navigation.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        navigation, "_camera_height_above_ground", lambda *_: 0.6
    )
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
