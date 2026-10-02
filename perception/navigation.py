"""
navigation.py — STUDENT C OWNS THIS FILE (other half of Task 4, 60% w/ perception).

goto_object() implements the search/steer/approach behavior and is called
by the Task 3 executor whenever a GotoObjectCommand is popped. It depends
ONLY on SkillsAPI and PerceptionAPI (never on skills_real / perception_real
directly), so you can develop and unit-test it entirely against
skills_mock.MockSkills before Student A's simulation exists:

    python tests/test_navigation_with_mock.py

Ground-truth object positions (config.OBJECT_POSITIONS) are used only for
the [FOUND] distance log. Navigation and the found decision use a calibrated
range estimate from the live detection bounding box.
"""

import json
import math
import time
from core.interfaces import SkillsAPI, PerceptionAPI
from core.schema import RobotPose
from core import config

_CAMERA_VERTICAL_FOV_DEG = 80.0
_CAMERA_DOWN_PITCH_DEG = 14.0
_CAMERA_HEIGHT_ABOVE_TRUNK_M = 0.16
_DEFAULT_TRUNK_HEIGHT_M = 0.45
_CAMERA_FORWARD_OFFSET_M = 0.58


def goto_object(object_class: str, color: str,
                 skills: SkillsAPI, perception: PerceptionAPI,
                 command_text: str | None = None) -> bool:
    """Runs the full search -> steer -> approach -> stop behavior.
    Returns True iff the target is visible when stopped within the estimated
    found distance."""
    if command_text is not None:
        print(
            f"[CMD] input={json.dumps(command_text)} "
            f"action=goto_object(class={object_class}, color={color})"
        )
    else:
        print(f"[CMD] action=goto_object(class={object_class}, color={color})")

    t0 = time.time()
    consecutive_misses = 0
    scan_degrees = 0.0
    target_acquired = False
    initial_center_scan_complete = False
    target_position = None
    post_strafe_reacquire = False
    reacquire_misses = 0
    reacquire_attempts = 0
    forward_attempt_start: RobotPose | None = None
    forward_attempt_started_at: float | None = None
    forward_attempt_duration = 0.0

    def reacquire_sweep(attempt: int) -> None:
        nonlocal target_position
        nonlocal post_strafe_reacquire
        _reacquire_sweep(skills, attempt, target_position)
        target_position = None
        post_strafe_reacquire = True

    def recover_if_stuck() -> bool:
        nonlocal forward_attempt_start
        nonlocal forward_attempt_started_at
        nonlocal forward_attempt_duration
        if forward_attempt_start is None or forward_attempt_started_at is None:
            return False

        elapsed = time.monotonic() - forward_attempt_started_at
        if elapsed < config.APPROACH_STUCK_TIMEOUT_S:
            return False

        pose_after_step = skills.get_robot_pose()
        heading = math.radians(forward_attempt_start.yaw_deg)
        forward_progress = (
            (pose_after_step.x - forward_attempt_start.x) * math.cos(heading)
            + (pose_after_step.y - forward_attempt_start.y) * math.sin(heading)
        )
        commanded_distance = abs(config.APPROACH_VX) * forward_attempt_duration
        blocked = (
            commanded_distance > 0.0
            and forward_progress
            < commanded_distance * config.APPROACH_STUCK_PROGRESS_FRACTION
        )
        if blocked:
            print("[APPROACH] forward progress blocked for "
                  f"{config.APPROACH_STUCK_TIMEOUT_S:.0f} s; backing up "
                  "and strafing to retry")
            skills.move(
                vx=-abs(config.APPROACH_VX), vy=0.0, wz=0.0,
                duration=config.APPROACH_STEP_S,
            )
            reacquire_sweep(0)

        forward_attempt_start = None
        forward_attempt_started_at = None
        forward_attempt_duration = 0.0
        return blocked

    clear_target_history = getattr(perception, "clear_target_history", None)
    if callable(clear_target_history):
        clear_target_history()

    while time.time() - t0 < config.APPROACH_TIMEOUT_S:
        frame = skills.get_camera_frame()
        detections = perception.detect(frame)
        detected_target = _pick_target(detections, object_class, color)
        target = detected_target
        if detected_target is not None and post_strafe_reacquire:
            skills.stop()
            time.sleep(1.5)
            frame = skills.get_camera_frame()
            detections = perception.detect(frame)
            target = _pick_target(detections, object_class, color)
            if target is None:
                continue
            post_strafe_reacquire = False
            target_position = None

        remember_target = getattr(perception, "remember_target", None)
        if target is not None:
            target_acquired = True
            consecutive_misses = 0
            reacquire_misses = 0
            reacquire_attempts = 0
            if callable(remember_target):
                remember_target(frame, target)
        elif target_acquired:
            reacquire_misses += 1
            if reacquire_misses >= config.REACQUIRE_MISSES:
                if reacquire_attempts >= config.REACQUIRE_MAX_ATTEMPTS:
                    print("[SEARCH] re-acquire failed, falling back to rotating search")
                    target_acquired = False
                    initial_center_scan_complete = False
                    target_position = None
                    reacquire_misses = 0
                    reacquire_attempts = 0
                    consecutive_misses = 0
                    forward_attempt_start = None
                    forward_attempt_started_at = None
                    forward_attempt_duration = 0.0
                    continue

                reacquire_sweep(reacquire_attempts)
                reacquire_attempts += 1
                reacquire_misses = 0
                forward_attempt_start = None
                forward_attempt_started_at = None
                forward_attempt_duration = 0.0
                continue

            recover_target = getattr(perception, "recover_target", None)
            if callable(recover_target):
                target = recover_target(frame, object_class, color)

        if recover_if_stuck():
            continue

        if target is None:
            if target_acquired:
                time.sleep(0.1)  # frames update at ~15 Hz; don't spin on the same one
                continue

            consecutive_misses += 1
            if consecutive_misses >= config.MAX_MISSES_BEFORE_LOST:
                print("[SEARCH] target not visible, rotating")
                skills.turn(config.SEARCH_TURN_DEG)
                scan_degrees += abs(config.SEARCH_TURN_DEG)
                if scan_degrees >= 360.0:
                    print("[MISSION] status=FAIL reason=target_not_found")
                    skills.stop()
                    return False
                consecutive_misses = 0
            continue

        target_acquired = True
        consecutive_misses = 0

        if not _steer_to_center(target, skills, frame.shape[1]):
            # Centering time is part of the same forward-stall deadline.
            if recover_if_stuck():
                continue
            continue
        if recover_if_stuck():
            continue

        if not initial_center_scan_complete:
            skills.stop()
            time.sleep(1.5)
            frame = skills.get_camera_frame()
            detections = perception.detect(frame)
            target = _pick_target(detections, object_class, color)
            if target is None:
                continue
            if callable(remember_target):
                remember_target(frame, target)

            if not _steer_to_center(target, skills, frame.shape[1]):
                continue
            initial_center_scan_complete = True

        pose = skills.get_robot_pose()
        camera_height = _camera_height_above_ground(skills)
        if target_position is None:
            target_position = _estimated_target_position(
                pose, target, frame.shape, camera_height
            )
        distance = _estimated_planar_distance(
            pose, target, frame.shape, camera_height, target_position
        )
        ground_truth_distance = _ground_truth_distance(
            pose, object_class, color
        )
        print(f"[RANGE] estimated_planar={distance:.2f} m "
              f"ground_truth={ground_truth_distance:.2f} m phase=approach")
        if distance <= config.FOUND_DISTANCE_M:
            if _finish_if_found(
                    skills, perception, object_class, color, t0,
                    target_position):
                return True
            print("[MISSION] status=FAIL reason=stop_verification")
            skills.stop()
            return False

        if forward_attempt_start is None:
            forward_attempt_start = pose
            forward_attempt_started_at = time.monotonic()
        step_duration = _approach_step(skills, distance)
        if step_duration > 0.0:
            forward_attempt_duration += step_duration
            if recover_if_stuck():
                continue
        else:
            forward_attempt_start = None
            forward_attempt_started_at = None
            forward_attempt_duration = 0.0

    print("[MISSION] status=FAIL reason=timeout")
    skills.stop()
    return False


def _pick_target(detections, object_class: str, color: str):
    for d in detections:
        if d.class_name == object_class and d.color == color:
            return d
    return None


def _steer_to_center(detection, skills: SkillsAPI,
                     frame_width: int = 320) -> bool:
    """Turn toward the bbox center, returning True once roughly centered."""
    x1, _, x2, _ = detection.bbox
    bbox_center_x = (x1 + x2) / 2.0
    offset_x = bbox_center_x - frame_width / 2.0

    if abs(offset_x) <= config.CENTER_TOLERANCE_PX:
        return True

    # Positive angles turn left, so a target right of center needs a right turn.
    correction_deg = min(5.0, abs(offset_x) / (frame_width / 2.0) * 30.0)
    skills.turn(-correction_deg if offset_x > 0 else correction_deg)
    return False

def _reacquire_sweep(skills: SkillsAPI, attempt: int, target_position) -> None:
    """Strafe to look around an occluder, then re-face the remembered target.
    Direction alternates and amplitude grows: L 1x, R 2x, L 3x, R 4x
    (net offset stays within about +/-1 base sweep, so it doesn't wander off)."""
    side = 1.0 if attempt % 2 == 0 else -1.0  # +vy = left
    duration = config.REACQUIRE_STRAFE_S * (attempt + 1)
    print(f"[SEARCH] target lost, strafing {'left' if side > 0 else 'right'} "
          f"{duration:.1f} s (attempt {attempt + 1}/{config.REACQUIRE_MAX_ATTEMPTS})")
    skills.move(vx=0.0, vy=side * config.REACQUIRE_STRAFE_VY, wz=0.0,
                duration=duration)
    skills.stop()
    time.sleep(0.4)  # let the gait settle and a fresh frame render

    if target_position is not None:
        pose = skills.get_robot_pose()
        bearing = math.degrees(math.atan2(target_position[1] - pose.y,
                                          target_position[0] - pose.x))
        err = (bearing - pose.yaw_deg + 180.0) % 360.0 - 180.0
        if abs(err) > 3.0:
            skills.turn(err)
        time.sleep(0.3)

def _approach_step(skills: SkillsAPI, distance: float) -> float:
    if distance <= config.FOUND_DISTANCE_M:
        skills.stop()
        return 0.0

    approach_vx = abs(config.APPROACH_VX)
    normal_step_distance = approach_vx * config.APPROACH_STEP_S
    step_distance = min(
        normal_step_distance,
        distance - config.FOUND_DISTANCE_M,
    )

    step_duration = step_distance / approach_vx
    skills.move(vx=approach_vx, vy=0.0, wz=0.0,
                duration=step_duration)
    return step_duration


def _camera_height_above_ground(skills: SkillsAPI) -> float:
    get_trunk_height = getattr(skills, "get_trunk_height", None)
    if callable(get_trunk_height):
        try:
            trunk_height = float(get_trunk_height())
        except (AttributeError, NotImplementedError, TypeError, ValueError):
            pass
        else:
            if math.isfinite(trunk_height) and trunk_height > 0.0:
                return trunk_height + _CAMERA_HEIGHT_ABOVE_TRUNK_M
    return _DEFAULT_TRUNK_HEIGHT_M + _CAMERA_HEIGHT_ABOVE_TRUNK_M


def _estimated_planar_distance(pose: RobotPose, detection,
                               frame_shape,
                               camera_height: float = (
                                   _DEFAULT_TRUNK_HEIGHT_M
                                   + _CAMERA_HEIGHT_ABOVE_TRUNK_M
                               ),
                               target_position: tuple | None = None) -> float:
    """Estimate range from a fixed target point or the current bbox."""
    if target_position is None:
        target_position = _estimated_target_position(
            pose, detection, frame_shape, camera_height
        )
    if target_position is None:
        return float("inf")
    return math.hypot(
        pose.x - target_position[0], pose.y - target_position[1]
    )


def _estimated_target_position(pose: RobotPose, detection, frame_shape,
                               camera_height: float) -> tuple | None:
    """Project the bbox's ground contact point into world coordinates."""
    frame_height, frame_width = frame_shape[:2]
    if frame_height <= 0 or frame_width <= 0:
        return None

    focal_length_px = frame_height / (
        2.0 * math.tan(math.radians(_CAMERA_VERTICAL_FOV_DEG) / 2.0)
    )
    bbox_center_x = (detection.bbox[0] + detection.bbox[2]) / 2.0
    bbox_bottom_y = min(max(detection.bbox[3], 0.0), float(frame_height))
    image_down_angle = math.atan(
        (bbox_bottom_y - frame_height / 2.0) / focal_length_px
    )
    ray_down_angle = math.radians(_CAMERA_DOWN_PITCH_DEG) + image_down_angle
    if not 0.0 < ray_down_angle < math.pi / 2.0:
        return None

    camera_forward = camera_height / math.tan(ray_down_angle)
    bearing = math.atan(
        (bbox_center_x - frame_width / 2.0) / focal_length_px
    )
    target_forward = camera_forward + _CAMERA_FORWARD_OFFSET_M
    target_left = -camera_forward * math.tan(bearing)

    yaw = math.radians(pose.yaw_deg)
    object_x = pose.x + target_forward * math.cos(yaw) \
        - target_left * math.sin(yaw)
    object_y = pose.y + target_forward * math.sin(yaw) \
        + target_left * math.cos(yaw)
    return object_x, object_y


def _finish_if_found(skills, perception, object_class, color, t0,
                     target_position) -> bool:

    skills.stop()
    time.sleep(0.4)  # let the gait settle and a fresh frame render

    frame = skills.get_camera_frame()
    detections = perception.detect(
        frame, conf_threshold=config.FOUND_DETECTION_CONF_THRESHOLD
    )
    target = _pick_target(detections, object_class, color)
    recover_target = getattr(perception, "recover_target", None)
    if callable(recover_target):
        recovered_target = None
        for detection in detections:
            recovered_target = recover_target(
                frame, object_class, color, search_bbox=detection.bbox
            )
            if recovered_target is not None:
                if (detection.class_name != object_class
                        or detection.color != color):
                    print(
                        f"[TRACK] final label corrected "
                        f"from={detection.class_name}/{detection.color} "
                        f"to={object_class}/{color}"
                    )
                break

        if recovered_target is not None:
            target = recovered_target
        elif not detections:
            target = recover_target(frame, object_class, color)
        elif target is None:
            print("[TRACK] final label conflict not confirmed by target history")
    if target is None:                                       # C1: current-frame match required
        return False

    pose = skills.get_robot_pose()
    estimated_distance = _estimated_planar_distance(
        pose, target, frame.shape, target_position=target_position
    )
    d = _ground_truth_distance(pose, object_class, color)  # log only
    print(f"[RANGE] estimated_planar={estimated_distance:.2f} m "
          f"ground_truth={d:.2f} m phase=stop_check")
    if estimated_distance > config.FOUND_DISTANCE_M:  # C2
        return False

    print(f"[FOUND] class={object_class} color={color} "
          f"t={time.time() - t0:.1f} s d={d:.2f} m")          # C3
    print("[MISSION] status=SUCCESS")
    return True


def _ground_truth_distance(pose: RobotPose, object_class: str, color: str) -> float:
    """Planar ground-truth distance for the [FOUND] log only."""
    key = f"{color}_{object_class}"
    x_obj, y_obj = config.OBJECT_POSITIONS[key]
    x_base, y_base = pose.x, pose.y
    return ((x_base - x_obj) ** 2 + (y_base - y_obj) ** 2) ** 0.5
