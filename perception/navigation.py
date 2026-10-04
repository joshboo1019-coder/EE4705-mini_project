"""
Change contributed by Student B (assist), pending review by Student C:
reactive avoidance during the approach (branch iter/avoid,
docs/iter_avoid.md): a nearer non-target object estimated < 1.0 m ahead
within +/-25 deg of the heading triggers a sideways step ([AVOID] log line);
live detections and estimated ranges only.

Change contributed by Student B (assist), pending review by Student C:
colour-plate fallback + plate range model for "stop sign" targets (branch
iter/stopsign-plate, docs/iter_stopsign_plate.md; image pixels only).

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
# Stop-sign plate range model, planar trunk-to-sign range from the plate bbox
# (fitted offline on rendered dog-camera views, docs/iter_stopsign_plate.md):
#   whole plate in view:      d = A + B / bbox_height   (sd 0.07 m, centred)
#   plate cut by the top edge: d = A + B / bbox_width    (close range, +-0.2 m)
# B is in pixels for a 480-row frame.
_SIGN_RANGE_FROM_HEIGHT = (0.75, 91.2)
_SIGN_RANGE_FROM_WIDTH = (0.31, 94.4)
_SIGN_EDGE_PX = 1.0
# Close range: the plate rises out of the top of the frame. Once only its
# bottom strip (<= _SIGN_NEAR_STRIP_PX rows of a 480-row frame) is left, the
# sign is ~0.75-0.80 m away (renders + S3_05 logs): report _SIGN_NEAR_RANGE_M
# so the approach stops while the plate is still in view for the stop check.
_SIGN_NEAR_STRIP_PX = 40.0
_SIGN_NEAR_RANGE_M = 0.70
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
    avoid_state = {"steps": 0, "sides": {}}

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
    if object_class == "stop sign" and callable(
            getattr(perception, "detect_plate", None)):
        perception = _PlateFallbackPerception(perception, color)

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
                    if _occlusion_sidestep(skills, object_class, avoid_state):
                        scan_degrees = 0.0
                        consecutive_misses = 0
                        continue
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
        if object_class == "stop sign":
            # signs: re-range from every live plate bbox (keep the last
            # position when this frame gives none)
            target_position = _estimated_target_position(
                pose, target, frame.shape, camera_height
            ) or target_position
        elif target_position is None:
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

        # iter/avoid (Student B assist, pending review by Student C):
        # side-step a nearer non-target object in the path (live detections
        # and estimated ranges only), then continue the approach.
        if _avoid_obstacle_ahead(skills, perception, frame, detections, pose,
                                 object_class, color, target_position,
                                 distance, avoid_state):
            forward_attempt_start = None
            forward_attempt_started_at = None
            forward_attempt_duration = 0.0
            continue

        if forward_attempt_start is None:
            forward_attempt_start = pose
            forward_attempt_started_at = time.monotonic()
        step_duration = _approach_step(
            skills,
            _sign_creep_distance(object_class, target, distance,
                                 _approach_stop_m(object_class)),
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


class _PlateFallbackPerception:
    """Wraps the perception for a "stop sign" goal: when YOLO returns no
    stop sign of the requested colour, add the colour-plate detection
    (perception.detect_plate) so search/approach/stop run unchanged.
    Everything else is delegated."""

    def __init__(self, inner, color: str):
        self._inner = inner
        self._color = color

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def detect(self, frame, conf_threshold=None):
        if conf_threshold is None:
            detections = self._inner.detect(frame)
        else:
            detections = self._inner.detect(frame, conf_threshold=conf_threshold)
        if any(d.class_name == "stop sign" and d.color == self._color
               for d in detections):
            return detections
        plate = self._inner.detect_plate(frame, self._color)
        if plate is None:
            return detections
        return list(detections) + [plate]


def _sign_plate_uncut(detection, frame_shape) -> bool:
    frame_height, frame_width = frame_shape[:2]
    x1, y1, x2, y2 = detection.bbox
    return (y1 > _SIGN_EDGE_PX and y2 < frame_height - _SIGN_EDGE_PX
            and x1 > _SIGN_EDGE_PX and x2 < frame_width - _SIGN_EDGE_PX)


def _sign_planar_range(detection, frame_shape) -> float | None:
    """Planar trunk-to-sign range from the plate bbox size (model above)."""
    frame_height, frame_width = frame_shape[:2]
    x1, y1, x2, y2 = detection.bbox
    scale = frame_height / 480.0
    if _sign_plate_uncut(detection, frame_shape) and y2 - y1 > 0:
        a, b = _SIGN_RANGE_FROM_HEIGHT
        return a + b * scale / (y2 - y1)
    if (x1 > _SIGN_EDGE_PX and x2 < frame_width - _SIGN_EDGE_PX
            and x2 - x1 > 0):
        a, b = _SIGN_RANGE_FROM_WIDTH
        d = a + b * scale / (x2 - x1)
    else:
        d = None
    if y1 <= _SIGN_EDGE_PX and y2 <= _SIGN_NEAR_STRIP_PX * scale:
        return _SIGN_NEAR_RANGE_M if d is None else min(d, _SIGN_NEAR_RANGE_M)
    return d


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
    if detection.class_name == "stop sign":
        sign_range = _sign_planar_range(detection, frame_shape)
        if sign_range is None:
            return None
        camera_forward = max(sign_range - _CAMERA_FORWARD_OFFSET_M, 0.05)
    elif (abs(camera_height) <= _SAME_HEIGHT_TOLERANCE_M
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


# --- Reactive avoidance (iter/avoid) ----------------------------------------
# Change contributed by Student B (assist), pending review by Student C.
# During the approach, a NON-target object whose ESTIMATED range is below
# _AVOID_AHEAD_M and whose estimated bearing is within +/-_AVOID_CONE_DEG of
# the heading, while the target is estimated farther away, triggers a short
# sideways step away from it; the loop repeats until it leaves the cone.
# Inputs are the live detections (YOLO + the stop-sign colour-plate detector)
# and the robot's own pose; no simulator ground truth (docs/iter_avoid.md).
_AVOID_AHEAD_M = 1.0
_AVOID_CONE_DEG = 25.0
_AVOID_TARGET_MARGIN_M = 0.20    # obstacle must be this much nearer than the target
_AVOID_SAME_OBJECT_M = 0.45      # a detection this close to the target estimate is the target
_AVOID_STRAFE_VY = 0.3           # m/s sideways (+vy = left)
_AVOID_STRAFE_S = 0.5            # one side-step: ~0.15 m
_AVOID_MAX_STEPS = 12            # per goto_object (~1.8 m sideways in total)
_AVOID_PLATE_COLORS = ("red", "yellow", "green")
# Half-width priors per class for the cone test (an object is in the cone if
# any part of it is): chair seat 0.22 m + legs, ball radius, sign pole + margin
# (the plate is at 0.70-1.00 m, above the robot's body).
_AVOID_HALF_WIDTH_M = {"chair": 0.25, "sports ball": 0.11, "stop sign": 0.05}
# A chair close to the camera is often no longer detected (frame-filling,
# relabelled); keep its last live-estimated position for this long.
_AVOID_MEMORY_S = 6.0
# Close to a sign, the plate rises out of the top of the frame within a
# ~0.15 m band; once it is cut by the top edge, approach in short steps so
# the near-strip stop rule fires before the plate is lost (S3_05 dev runs).
_SIGN_CREEP_STEP_M = 0.07


def _sign_creep_distance(object_class, target, distance, stop_m):
    if (object_class == "stop sign" and target is not None
            and target.bbox[1] <= _SIGN_EDGE_PX):
        return min(distance, stop_m + _SIGN_CREEP_STEP_M)
    return distance


_OCCLUSION_SIDESTEP_CLASSES = ("stop sign",)  # thin, small targets hide behind a nearer object
_OCCLUSION_SIDESTEP_VY = 0.4     # m/s, +vy = left
_OCCLUSION_SIDESTEP_S = 2.0      # ~0.8 m sideways


def _occlusion_sidestep(skills, object_class: str, state) -> bool:
    """After a full in-place scan without the target: for a small/thin target
    class (a sign plate can sit right behind a nearer chair), step sideways
    once and let the caller scan again. Returns True if it stepped."""
    if object_class not in _OCCLUSION_SIDESTEP_CLASSES or state.get("sidestepped"):
        return False
    state["sidestepped"] = True
    print(f"[SEARCH] full scan without the target, side-stepping left "
          f"{_OCCLUSION_SIDESTEP_VY * _OCCLUSION_SIDESTEP_S:.1f} m to look past occluders")
    skills.move(vx=0.0, vy=_OCCLUSION_SIDESTEP_VY, wz=0.0,
                duration=_OCCLUSION_SIDESTEP_S)
    skills.stop()
    time.sleep(0.4)  # settle, fresh frame
    return True


def _avoid_decision(obstacles, target_distance: float,
                    target_bearing_deg: float = 0.0, sides=None):
    """Pure decision. `obstacles`: iterable of (label, d_est, bearing_deg
    [, half_width_deg]) with bearing relative to the heading (+ = left); an
    obstacle is in the cone if any part of it is. Returns
    (label, d_est, side) for the nearest obstacle that is within
    _AVOID_AHEAD_M, inside the +/-_AVOID_CONE_DEG cone and nearer than the
    target by _AVOID_TARGET_MARGIN_M; side is "L" or "R" (the direction to
    step: away from the obstacle, relative to the target line). `sides`
    keeps the first side chosen per label so the robot does not zig-zag."""
    best = None
    for obstacle in obstacles:
        label, d_est, bearing = obstacle[:3]
        half_deg = obstacle[3] if len(obstacle) > 3 else 0.0
        if not (math.isfinite(d_est) and math.isfinite(bearing)):
            continue
        if d_est >= _AVOID_AHEAD_M or abs(bearing) - half_deg > _AVOID_CONE_DEG:
            continue
        if not d_est < target_distance - _AVOID_TARGET_MARGIN_M:
            continue
        if best is None or d_est < best[1]:
            best = (label, d_est, bearing)
    if best is None:
        return None
    label, d_est, bearing = best
    side = (sides or {}).get(label)
    if side is None:
        side = "R" if bearing > target_bearing_deg else "L"
    return label, d_est, side


def _obstacle_estimates(skills, perception, frame, detections, pose,
                        object_class, color, target_position, memory=None):
    """(label, d_est, bearing_deg, half_width_deg) for each live non-target
    detection, ranged with the same bbox models as the target (no ground
    truth). `memory` (label -> (x, y, cls, time)) keeps each obstacle's last
    live estimate for _AVOID_MEMORY_S so a frame-filling chair that YOLO
    no longer reports is still avoided (the robot's own pose moves it)."""
    candidates = [d for d in detections
                  if d.class_name in _NOMINAL_CENTER_HEIGHTS_M
                  and not (d.class_name == object_class and d.color == color)]
    detect_plate = getattr(perception, "detect_plate", None)
    if callable(detect_plate):
        for plate_color in _AVOID_PLATE_COLORS:
            if object_class == "stop sign" and plate_color == color:
                continue
            if any(d.class_name == "stop sign" and d.color == plate_color
                   for d in candidates):
                continue
            plate = detect_plate(frame, plate_color)
            if plate is not None:
                candidates.append(plate)
    out = []
    now = time.monotonic()
    seen = set()
    for det in candidates:
        camera_height = _camera_height_above_ground(
            skills, det.class_name, det.color, det, frame.shape)
        position = _estimated_target_position(pose, det, frame.shape,
                                              camera_height)
        if position is None:
            continue
        if (target_position is not None
                and math.hypot(position[0] - target_position[0],
                               position[1] - target_position[1])
                < _AVOID_SAME_OBJECT_M):
            continue
        label = f"{det.color} {det.class_name}"
        seen.add(label)
        if memory is not None:
            memory[label] = (position[0], position[1], det.class_name, now)
        out.append(_relative_obstacle(label, det.class_name, position, pose))
    if memory is not None:
        for label, (x, y, cls, stamp) in list(memory.items()):
            if now - stamp > _AVOID_MEMORY_S:
                del memory[label]
            elif label not in seen:
                out.append(_relative_obstacle(label, cls, (x, y), pose))
    return out


def _relative_obstacle(label, object_class, position, pose):
    d_est = math.hypot(position[0] - pose.x, position[1] - pose.y)
    bearing = math.degrees(math.atan2(position[1] - pose.y,
                                      position[0] - pose.x))
    bearing = (bearing - pose.yaw_deg + 180.0) % 360.0 - 180.0
    half = _AVOID_HALF_WIDTH_M.get(object_class, 0.0)
    half_deg = math.degrees(math.atan2(half, max(d_est, 1e-3)))
    return (label, d_est, bearing, half_deg)


def _avoid_obstacle_ahead(skills, perception, frame, detections, pose,
                          object_class, color, target_position,
                          target_distance, state) -> bool:
    """One avoidance step if needed: log [AVOID], side-step, return True."""
    if state["steps"] >= _AVOID_MAX_STEPS:
        return False
    obstacles = _obstacle_estimates(skills, perception, frame, detections,
                                    pose, object_class, color,
                                    target_position,
                                    state.setdefault("memory", {}))
    target_bearing = 0.0
    if target_position is not None:
        target_bearing = math.degrees(math.atan2(
            target_position[1] - pose.y, target_position[0] - pose.x))
        target_bearing = (target_bearing - pose.yaw_deg + 180.0) % 360.0 - 180.0
    decision = _avoid_decision(obstacles, target_distance, target_bearing,
                               state["sides"])
    if decision is None:
        return False
    label, d_est, side = decision
    state["sides"].setdefault(label, side)
    state["steps"] += 1
    print(f"[AVOID] obj={label} d_est={d_est:.2f} side={side}")
    vy = _AVOID_STRAFE_VY if side == "L" else -_AVOID_STRAFE_VY
    skills.move(vx=0.0, vy=vy, wz=0.0, duration=_AVOID_STRAFE_S)
    skills.stop()
    time.sleep(0.3)  # settle, fresh frame
    return True


def _ground_truth_distance(pose: RobotPose, object_class: str, color: str) -> float:
    """Planar ground-truth distance for the [FOUND] log only."""
    key = f"{color}_{object_class}"
    x_obj, y_obj = config.OBJECT_POSITIONS[key]
    x_base, y_base = pose.x, pose.y
    return ((x_base - x_obj) ** 2 + (y_base - y_obj) ** 2) ** 0.5
