"""
navigation.py — STUDENT C OWNS THIS FILE (other half of Task 4, 60% w/ perception).

goto_object() implements the search/steer/approach behavior and is called
by the Task 3 executor whenever a GotoObjectCommand is popped. It depends
ONLY on SkillsAPI and PerceptionAPI (never on skills_real / perception_real
directly), so you can develop and unit-test it entirely against
skills_mock.MockSkills before Student A's simulation exists:

    python tests/test_navigation_with_mock.py

Ground-truth object positions (config.OBJECT_POSITIONS, filled in by
Student A during Task 2 scene building) are used ONLY for the planar
distance check and [FOUND] log — never to steer the robot.
"""

import time
from core.interfaces import SkillsAPI, PerceptionAPI
from core.schema import RobotPose
from core import config


def goto_object(object_class: str, color: str,
                 skills: SkillsAPI, perception: PerceptionAPI) -> bool:
    """Runs the full search -> steer -> approach -> stop behavior.
    Returns True iff the target is visible when stopped within found distance."""
    t0 = time.time()
    consecutive_misses = 0
    target_acquired = False
    target_centered = False
    last_steer_direction = 0.0
    centering_retries = 0
    target_history = []

    while time.time() - t0 < config.APPROACH_TIMEOUT_S:
        frame = skills.get_camera_frame()
        detections = perception.detect(frame)
        target = _pick_target(detections, object_class, color)
        if target is not None:
            _remember_target(frame, target, target_history)
        elif target_acquired:
            target = _recover_target(frame, target_history,
                                     object_class, color)

        if target is None:
            if target_acquired:
                consecutive_misses += 1
                if not target_centered and last_steer_direction != 0.0 \
                        and consecutive_misses >= 2:
                    if centering_retries < 3:
                        skills.turn(2.0 * last_steer_direction)
                        centering_retries += 1
                    else:
                        pose, distance = _approach_steps(
                            skills, object_class, color, steps=2
                        )
                        if _finish_if_found(
                                skills, perception, object_class, color,
                            distance, t0, target_history):
                            return True
                        if distance <= config.FOUND_DISTANCE_M:
                            print("[MISSION] status=FAIL reason=stop_verification")
                            return False
                        target_centered = True
                        centering_retries = 0
                    consecutive_misses = 0
                elif target_centered and consecutive_misses >= config.MAX_MISSES_BEFORE_LOST:
                    pose, distance = _approach_steps(
                        skills, object_class, color, steps=2
                    )
                    if _finish_if_found(
                            skills, perception, object_class, color,
                            distance, t0, target_history):
                        return True
                    if distance <= config.FOUND_DISTANCE_M:
                        print("[MISSION] status=FAIL reason=stop_verification")
                        return False
                    consecutive_misses = 0
                continue

            consecutive_misses += 1
            if consecutive_misses >= config.MAX_MISSES_BEFORE_LOST:
                print("[SEARCH] target not visible, rotating")
                skills.turn(config.SEARCH_TURN_DEG)
                consecutive_misses = 0
            continue

        target_acquired = True
        consecutive_misses = 0
        centering_retries = 0

        x1, _, x2, _ = target.bbox
        offset_x = (x1 + x2) / 2.0 - frame.shape[1] / 2.0
        target_centered = abs(offset_x) <= config.CENTER_TOLERANCE_PX
        if not target_centered:
            last_steer_direction = -1.0 if offset_x > 0 else 1.0
        else:
            last_steer_direction = 0.0

        if not _steer_to_center(target, skills, frame.shape[1]):
            # not centered yet — small turn step and re-detect next loop
            continue

        # Advance in short steps, rechecking the stopping distance after each.
        pose, distance = _approach_steps(
            skills, object_class, color, steps=2
        )
        if _finish_if_found(
                skills, perception, object_class, color,
            distance, t0, target_history):
            return True
        if distance <= config.FOUND_DISTANCE_M:
            print("[MISSION] status=FAIL reason=stop_verification")
            return False

    print("[MISSION] status=FAIL reason=timeout")
    skills.stop()
    return False


def _pick_target(detections, object_class: str, color: str):
    for d in detections:
        if d.class_name == object_class and d.color == color:
            return d
    return None


def _remember_target(frame, detection, history) -> None:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return

    rgb_frame = np.asarray(frame, dtype=np.uint8)
    success, encoded = cv2.imencode(
        ".png", cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)
    )
    if not success:
        return

    history.append((encoded.tobytes(), tuple(detection.bbox)))
    del history[:-5]


def _recover_target(frame, history, object_class: str, color: str):
    if not history:
        return None

    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    current = np.asarray(frame, dtype=np.uint8)
    frame_height, frame_width = current.shape[:2]
    best_match = None

    for encoded, bbox in reversed(history):
        reference_bgr = cv2.imdecode(
            np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        if reference_bgr is None:
            continue
        reference = cv2.cvtColor(reference_bgr, cv2.COLOR_BGR2RGB)
        ref_height, ref_width = reference.shape[:2]
        x1, y1, x2, y2 = bbox
        x1 = max(0, min(ref_width, int(x1)))
        y1 = max(0, min(ref_height, int(y1)))
        x2 = max(x1, min(ref_width, int(x2)))
        y2 = max(y1, min(ref_height, int(y2)))
        target_crop = reference[y1:y2, x1:x2]
        crop_height, crop_width = target_crop.shape[:2]
        if crop_width < 20 or crop_height < 20:
            continue

        patch_width = max(16, int(crop_width * 0.6))
        patch_height = max(16, int(crop_height * 0.6))
        x_positions = sorted({0, (crop_width - patch_width) // 2,
                              crop_width - patch_width})
        y_positions = sorted({0, (crop_height - patch_height) // 2,
                              crop_height - patch_height})
        patches = [
            (target_crop[py:py + patch_height, px:px + patch_width], px, py)
            for px, py in ((x_positions[0], y_positions[0]),
                           (x_positions[-1], y_positions[0]),
                           (x_positions[0], y_positions[-1]),
                           (x_positions[-1], y_positions[-1]),
                           (x_positions[1], y_positions[1]))
        ]

        for patch, patch_x, patch_y in patches:
            if float(np.std(patch)) < 5.0:
                continue
            for scale in (0.75, 1.0, 1.25, 1.5, 2.0):
                scaled_width = int(patch.shape[1] * scale)
                scaled_height = int(patch.shape[0] * scale)
                if scaled_width > frame_width or scaled_height > frame_height:
                    continue
                interpolation = (cv2.INTER_AREA if scale < 1.0
                                 else cv2.INTER_LINEAR)
                template = cv2.resize(
                    patch, (scaled_width, scaled_height),
                    interpolation=interpolation,
                )
                scores = cv2.matchTemplate(
                    current, template, cv2.TM_CCOEFF_NORMED
                )
                _, score, _, location = cv2.minMaxLoc(scores)
                if score < 0.78 or _target_color_fraction(
                        current[location[1]:location[1] + scaled_height,
                                location[0]:location[0] + scaled_width],
                        color, cv2) < 0.10:
                    continue

                candidate = (score, location, scale, patch_x, patch_y,
                             crop_width, crop_height, scaled_width,
                             scaled_height)
                if best_match is None or score > best_match[0]:
                    best_match = candidate

    if best_match is None:
        return None

    score, location, scale, patch_x, patch_y, crop_width, crop_height, _, _ = best_match
    recovered_x1 = max(0.0, location[0] - patch_x * scale)
    recovered_y1 = max(0.0, location[1] - patch_y * scale)
    recovered_x2 = min(frame_width, recovered_x1 + crop_width * scale)
    recovered_y2 = min(frame_height, recovered_y1 + crop_height * scale)
    print(f"[TRACK] recovered partial {color} {object_class} "
          f"from stored frame score={score:.2f}")
    from core.schema import Detection
    return Detection(
        class_name=object_class,
        color=color,
        conf=float(score),
        bbox=(recovered_x1, recovered_y1, recovered_x2, recovered_y2),
    )


def _target_color_fraction(region, color: str, cv2) -> float:
    import numpy as np

    if region.size == 0:
        return 0.0
    hsv = cv2.cvtColor(region, cv2.COLOR_RGB2HSV)
    hue = hsv[..., 0]
    saturation = hsv[..., 1]
    value = hsv[..., 2]
    valid = (saturation >= 64) & (value >= 32)
    if color == "red":
        matches = (hue < 8) | (hue >= 173)
    elif color == "orange":
        matches = (hue >= 8) & (hue < 23)
    elif color == "yellow":
        matches = (hue >= 23) & (hue < 35)
    elif color == "green":
        matches = (hue >= 35) & (hue < 80)
    elif color == "blue":
        matches = (hue >= 80) & (hue < 130)
    elif color == "purple":
        matches = (hue >= 130) & (hue < 145)
    elif color == "pink":
        matches = (hue >= 145) & (hue < 173)
    else:
        return 0.0
    return float(np.count_nonzero(matches & valid) / region.shape[0] / region.shape[1])


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


def _approach_steps(skills: SkillsAPI, object_class: str, color: str,
                    steps: int):
    pose = skills.get_robot_pose()
    distance = _ground_truth_distance(pose, object_class, color)
    for _ in range(steps):
        skills.move(vx=config.APPROACH_VX, vy=0.0, wz=0.0,
                    duration=config.APPROACH_STEP_S)
        pose = skills.get_robot_pose()
        distance = _ground_truth_distance(pose, object_class, color)
        if distance <= config.FOUND_DISTANCE_M:
            skills.stop()
            break
    return pose, distance


def _finish_if_found(skills: SkillsAPI, perception: PerceptionAPI,
                     object_class: str, color: str, distance: float,
                     t0: float, target_history) -> bool:
    if distance > config.FOUND_DISTANCE_M:
        return False

    skills.stop()
    pose = skills.get_robot_pose()
    frame = skills.get_camera_frame()
    detections = perception.detect(frame)
    target = _pick_target(detections, object_class, color)
    if target is None:
        target = _recover_target(frame, target_history, object_class, color)
    if target is None:
        return False

    elapsed = time.time() - t0
    print(f"[FOUND] class={object_class} color={color} "
          f"t={elapsed:.1f} s d={distance:.2f} m")
    print("[MISSION] status=SUCCESS")
    return True


def _ground_truth_distance(pose: RobotPose, object_class: str, color: str) -> float:
    """Planar trunk-to-object distance for the [FOUND] check and log only."""
    key = f"{color}_{object_class}"
    x_obj, y_obj = config.OBJECT_POSITIONS[key]
    x_base, y_base = pose.x, pose.y
    return ((x_base - x_obj) ** 2 + (y_base - y_obj) ** 2) ** 0.5
