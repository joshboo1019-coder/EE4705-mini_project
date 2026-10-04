"""
Change contributed by Student B (assist), pending review by Student C:
the approach stops at config.APPROACH_STOP_M (docs/task4_c2_margin.md);
no simulator ground truth in the range estimate (assist/no-gt-height,
docs/task4_no_gt_height.md): the target's height comes from nominal
per-class floor heights or from the bbox, never from data.xpos.

navigation.py — STUDENT C OWNS THIS FILE (other half of Task 4, 60% w/ perception).

goto_object() implements the search/steer/approach behavior and is called
by the Task 3 executor whenever a GotoObjectCommand is popped. It depends
ONLY on SkillsAPI and PerceptionAPI (never on skills_real / perception_real
directly), so you can develop and unit-test it entirely against
skills_mock.MockSkills before Student A's simulation exists:

    python tests/test_navigation_with_mock.py

Ground-truth object positions (config.OBJECT_POSITIONS) are used only for
the [FOUND] distance log (and the [RANGE] ground_truth= field). Navigation
and the found decision use a calibrated range estimate from the live
detection bounding box and the robot's own trunk height; nothing reads the
target's simulator state.
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
_CAMERA_FORWARD_OFFSET_M = 0.45
# Height of the bbox centre above the floor for a target standing on the
# floor, per class (chair: 0.88 m tall, centre 0.44; ball: radius 0.11;
# stop sign: Student C's 0.50). These are prior knowledge of the object
# classes, not simulator state.
_NOMINAL_CENTER_HEIGHTS_M = {
    "chair": 0.44,
    "sports ball": 0.11,
    "stop sign": 0.50,
}
# Classes whose elevation is estimated from the bbox (their nominal height is
# the centre of their full-height bbox). Signs keep the nominal height.
_ELEVATION_CLASSES = ("chair", "sports ball")
_ELEVATED_THRESHOLD_M = 0.20     # bbox-centre height this far above nominal = elevated
_ELEVATION_MIN_BBOX_PX = 24
_ELEVATION_EDGE_MARGIN_PX = 2.0
_TARGET_HEIGHTS_M = {
    "chair": 0.88,
    "sports ball": 0.22,
    "stop sign": 0.30,
}
_SAME_HEIGHT_TOLERANCE_M = 0.03
_NEAR_HORIZONTAL_RAY_ANGLE_DEG = 5.0

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
    # iter/chair-safety: the robot's own last range ESTIMATE to the target
    # (never ground truth) and the estimated target point it came from.
    last_estimated_distance = math.inf
    last_target_position = None

    def reacquire_sweep(attempt: int) -> None:
        nonlocal target_position
        nonlocal post_strafe_reacquire
        nonlocal last_estimated_distance
        if _too_close_to_strafe(last_estimated_distance, object_class):
            # Target lost close-up: never strafe (or advance) next to it;
            # back off, then rotate in place to re-acquire.
            last_estimated_distance = _close_range_reacquire(
                skills, perception, object_class, color, attempt,
                last_target_position, last_estimated_distance)
        else:
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
            if not _too_close_to_strafe(last_estimated_distance, object_class):
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
        camera_height = _camera_height_above_ground(
            skills, target.class_name, target.color, target, frame.shape
        )
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
        if math.isfinite(distance):
            last_estimated_distance = distance
            last_target_position = target_position
        if distance <= _approach_stop_m(object_class):
            if _finish_if_found(
                    skills, perception, object_class, color, t0,
                    target_position):
                return True
            if _reverify_after_backoff(
                    skills, perception, object_class, color, t0,
                    target_position):
                return True
            print("[MISSION] status=FAIL reason=stop_verification")
            skills.stop()
            return False

        if (detected_target is None
                and _too_close_to_strafe(last_estimated_distance, object_class)):
            # Detector lost it close-up (tracker-only target): do not step
            # toward it; wait for a live detection or the close-range
            # re-acquire (back off + rotate in place).
            time.sleep(0.1)
            continue

        if forward_attempt_start is None:
            forward_attempt_start = pose
            forward_attempt_started_at = time.monotonic()
        step_duration = _approach_step(skills, distance,
                                       _approach_stop_m(object_class))
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

def _too_close_to_strafe(estimated_distance: float,
                         object_class: str | None = None) -> bool:
    """True when the robot's own last range ESTIMATE (not ground truth) is
    within CLOSE_REACQUIRE_MARGIN_M of the class's stop distance: too close
    to strafe or advance blind next to the target (iter/chair-safety: the red
    chair was touched during the re-acquire strafe after it was lost
    close-up). Change contributed by Student B (assist), pending review by
    Student C."""
    margin = float(getattr(config, "CLOSE_REACQUIRE_MARGIN_M", 0.15))
    return estimated_distance < _approach_stop_m(object_class) + margin


def _close_range_reacquire(skills: SkillsAPI, perception: PerceptionAPI,
                           object_class: str, color: str, attempt: int,
                           target_position, estimated_distance: float) -> float:
    """Re-acquire a target lost close-up without touching it: back off
    CLOSE_REACQUIRE_BACKOFF_M (>= 0.25 m) straight back with the move skill,
    then rotate IN PLACE only — re-face the remembered (estimated) target
    point, then scan +/- CLOSE_REACQUIRE_SCAN_DEG (growing per attempt) —
    stopping at the first heading with a live detection. No strafe, no
    forward motion. Returns the new range estimate (robot pose to the
    estimated target point; never ground truth).
    Change contributed by Student B (assist), pending review by Student C."""
    backoff = max(0.25, float(getattr(config, "CLOSE_REACQUIRE_BACKOFF_M", 0.25)))
    base_scan = float(getattr(config, "CLOSE_REACQUIRE_SCAN_DEG", 20.0))
    scan = min(base_scan * (attempt + 1), 60.0)
    print(f"[REACQUIRE] target lost close-up (estimated {estimated_distance:.2f} m"
          f" < stop {_approach_stop_m(object_class):.2f} m"
          f" + {float(getattr(config, 'CLOSE_REACQUIRE_MARGIN_M', 0.15)):.2f} m);"
          f" backing off {backoff:.2f} m, rotating in place +/-{scan:.0f} deg"
          f" (attempt {attempt + 1}/{config.REACQUIRE_MAX_ATTEMPTS})")
    vx = abs(config.APPROACH_VX)
    skills.move(vx=-vx, vy=0.0, wz=0.0, duration=backoff / vx)
    skills.stop()
    time.sleep(0.4)  # let the gait settle and a fresh frame render

    pose = skills.get_robot_pose()
    new_estimate = estimated_distance + backoff
    if target_position is not None:
        new_estimate = math.hypot(target_position[0] - pose.x,
                                  target_position[1] - pose.y)
        bearing = math.degrees(math.atan2(target_position[1] - pose.y,
                                          target_position[0] - pose.x))
        err = (bearing - pose.yaw_deg + 180.0) % 360.0 - 180.0
        if abs(err) > 3.0:
            skills.turn(err)

    turned = 0.0
    for offset in (0.0, scan, -2.0 * scan):
        if offset:
            skills.turn(offset)
            turned += offset
        time.sleep(0.4)  # settle, fresh frame
        frame = skills.get_camera_frame()
        if _pick_target(perception.detect(frame), object_class, color) is not None:
            print(f"[REACQUIRE] target re-acquired after rotating {turned:+.0f} deg")
            return new_estimate
    if turned:
        skills.turn(-turned)  # back to the re-faced heading
    return new_estimate


def _approach_stop_m(object_class: str | None = None) -> float:
    """Where the approach stops (estimated range), per target class. Below
    FOUND_DISTANCE_M by a margin for that class's range-estimate error, so
    the TRUE distance is within FOUND_DISTANCE_M (the evaluation definition,
    still used by the stop check C2 below); see docs/task4_c2_margin.md."""
    by_class = getattr(config, "APPROACH_STOP_M_BY_CLASS", {})
    if object_class in by_class:
        return by_class[object_class]
    return getattr(config, "APPROACH_STOP_M", config.FOUND_DISTANCE_M)


def _approach_step(skills: SkillsAPI, distance: float,
                   stop_m: float | None = None) -> float:
    if stop_m is None:
        stop_m = _approach_stop_m()
    if distance <= stop_m:
        skills.stop()
        return 0.0

    approach_vx = abs(config.APPROACH_VX)
    normal_step_distance = approach_vx * config.APPROACH_STEP_S
    step_distance = min(
        normal_step_distance,
        distance - stop_m,
    )

    step_duration = step_distance / approach_vx
    skills.move(vx=approach_vx, vy=0.0, wz=0.0,
                duration=step_duration)
    return step_duration


def _camera_height_above_ground(skills: SkillsAPI, object_class: str,
                                color: str, detection=None,
                                frame_shape=None) -> float:
    """Camera z minus the target centre's z, both in the world frame.

    The camera z comes from the robot's own measured trunk height
    (proprioception, like get_robot_pose). The target centre's z is NOT read
    from the simulator: it is the class's nominal floor height, or — when
    the live bbox says the target stands clearly higher (e.g. the blue chair
    on the stairs) — an estimate from the bbox (_target_center_height).
    `color` is unused (kept for callers)."""
    camera_z = _DEFAULT_TRUNK_HEIGHT_M + _CAMERA_HEIGHT_ABOVE_TRUNK_M
    get_trunk_height = getattr(skills, "get_trunk_height", None)
    if callable(get_trunk_height):
        try:
            trunk_height = float(get_trunk_height())
        except (AttributeError, NotImplementedError, TypeError, ValueError):
            pass
        else:
            if math.isfinite(trunk_height) and trunk_height > 0.0:
                camera_z = trunk_height + _CAMERA_HEIGHT_ABOVE_TRUNK_M
    return camera_z - _target_center_height(
        object_class, detection, frame_shape, camera_z)


def _target_center_height(object_class: str, detection, frame_shape,
                          camera_z: float) -> float:
    """World z of the target's bbox centre, without ground truth.

    Range the target by its known size (f * H / bbox height), then read
    the bbox centre's height off the ray through it:
        z = camera_z - range * tan(ray_down_angle)
    If that is more than _ELEVATED_THRESHOLD_M above the class's nominal
    floor height, the target stands on something (stairs) and the
    estimate is used; otherwise — and whenever the bbox is too small or cut
    by the frame edge, so its size can't be trusted — the nominal floor
    height is. Limitation: with the robot itself on the stairs, a floor
    target looks lower than nominal; that is not detected (the estimate
    only ever raises the target)."""
    nominal = _NOMINAL_CENTER_HEIGHTS_M.get(object_class, 0.0)
    if (detection is None or frame_shape is None
            or object_class not in _ELEVATION_CLASSES):
        return nominal
    frame_height = frame_shape[0]
    target_height = _TARGET_HEIGHTS_M.get(object_class)
    x1, y1, x2, y2 = detection.bbox
    bbox_height = y2 - y1
    if (target_height is None or frame_height <= 0
            or bbox_height < _ELEVATION_MIN_BBOX_PX
            or y1 <= _ELEVATION_EDGE_MARGIN_PX
            or y2 >= frame_height - _ELEVATION_EDGE_MARGIN_PX):
        return nominal
    focal_length_px = frame_height / (
        2.0 * math.tan(math.radians(_CAMERA_VERTICAL_FOV_DEG) / 2.0))
    camera_forward = focal_length_px * target_height / bbox_height
    image_down_angle = math.atan(((y1 + y2) / 2.0 - frame_height / 2.0)
                                 / focal_length_px)
    ray_down_angle = math.radians(_CAMERA_DOWN_PITCH_DEG) + image_down_angle
    estimate = camera_z - camera_forward * math.tan(ray_down_angle)
    if math.isfinite(estimate) and estimate - nominal >= _ELEVATED_THRESHOLD_M:
        return estimate
    return nominal


def _estimated_planar_distance(pose: RobotPose, detection,
                               frame_shape,
                               camera_height: float = (
                                   _DEFAULT_TRUNK_HEIGHT_M
                                   + _CAMERA_HEIGHT_ABOVE_TRUNK_M
                               ),
                               target_position: tuple | None = None) -> float:
    """Estimate horizontal range to a fixed target point or bbox center.

    `camera_height` is the signed vertical difference between the camera
    and the target center.
    """
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
    """Project the bbox into world coordinates with height-aware ranging.

    Near equal camera and target-center heights, or when the bbox-center ray
    is nearly horizontal, use the known target size because vertical-angle
    ranging is poorly conditioned. Otherwise, use the signed vertical angle.
    """
    frame_height, frame_width = frame_shape[:2]
    if frame_height <= 0 or frame_width <= 0:
        return None

    focal_length_px = frame_height / (
        2.0 * math.tan(math.radians(_CAMERA_VERTICAL_FOV_DEG) / 2.0)
    )
    x1, y1, x2, y2 = detection.bbox
    bbox_center_x = (x1 + x2) / 2.0
    bbox_center_y = min(max((y1 + y2) / 2.0, 0.0), float(frame_height))
    image_down_angle = math.atan(
        (bbox_center_y - frame_height / 2.0) / focal_length_px
    )
    ray_down_angle = math.radians(_CAMERA_DOWN_PITCH_DEG) + image_down_angle
    if (abs(camera_height) <= _SAME_HEIGHT_TOLERANCE_M
            or abs(ray_down_angle)
            <= math.radians(_NEAR_HORIZONTAL_RAY_ANGLE_DEG)):
        bbox_height = y2 - y1
        target_height = _TARGET_HEIGHTS_M.get(detection.class_name)
        if (bbox_height <= 0.0 or target_height is None
                or y1 <= 0.0 or y2 >= frame_height):
            return None
        camera_forward = focal_length_px * target_height / bbox_height
    else:
        if not 0.0 < abs(ray_down_angle) < math.pi / 2.0:
            return None
        camera_forward = camera_height / math.tan(ray_down_angle)

    if not math.isfinite(camera_forward) or camera_forward <= 0.0:
        return None
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
            # iter/close-range-c1 (Student B assist, pending review by Student C):
            # a frame-filling target is often mislabelled by YOLO ("bed") while the
            # tracker still re-identifies it in the live frame; try the whole live
            # frame once (C1 stays a live-frame detection, no ground truth).
            target = recover_target(frame, object_class, color)
            if target is not None:
                print("[TRACK] final label conflict resolved: target re-identified in the live frame")
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


def _reverify_after_backoff(skills, perception, object_class, color, t0,
                            target_position) -> bool:
    """One retry when the stop check fails (C1 lost / mislabelled at close
    range, e.g. a frame-filling chair labelled "bed", or C2): back up
    VERIFY_BACKOFF_M with the move skill, re-scan the heading and +/-
    VERIFY_SCAN_DEG, re-centre on the target and re-run the same stop check.
    Live frames and the robot's own pose only; no ground truth.
    Change contributed by Student B (assist), pending review by Student C."""
    backoff = float(getattr(config, "VERIFY_BACKOFF_M", 0.15))
    scan = float(getattr(config, "VERIFY_SCAN_DEG", 20.0))
    print(f"[VERIFY] retry=1 backoff={backoff:.2f}m")
    vx = abs(config.APPROACH_VX)
    skills.move(vx=-vx, vy=0.0, wz=0.0, duration=backoff / vx)
    skills.stop()
    turned = 0.0
    for offset in (0.0, scan, -2.0 * scan):
        if offset:
            skills.turn(offset)
            turned += offset
        time.sleep(0.4)  # settle, fresh frame
        frame = skills.get_camera_frame()
        target = _pick_target(
            perception.detect(frame, conf_threshold=config.FOUND_DETECTION_CONF_THRESHOLD),
            object_class, color)
        if target is None:
            continue
        for _ in range(3):  # re-centre (small steering turns)
            if _steer_to_center(target, skills, frame.shape[1]):
                break
            frame = skills.get_camera_frame()
            target = _pick_target(perception.detect(frame), object_class, color)
            if target is None:
                break
        return _finish_if_found(skills, perception, object_class, color, t0,
                                target_position)
    if turned:
        skills.turn(-turned)  # back to the original heading
    return False


def _ground_truth_distance(pose: RobotPose, object_class: str, color: str) -> float:
    """Planar ground-truth distance for the [FOUND] log only."""
    key = f"{color}_{object_class}"
    x_obj, y_obj = config.OBJECT_POSITIONS[key]
    x_base, y_base = pose.x, pose.y
    return ((x_base - x_obj) ** 2 + (y_base - y_obj) ** 2) ** 0.5
