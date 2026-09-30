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
    clear_target_history = getattr(perception, "clear_target_history", None)
    if callable(clear_target_history):
        clear_target_history()

    while time.time() - t0 < config.APPROACH_TIMEOUT_S:
        frame = skills.get_camera_frame()
        detections = perception.detect(frame)
        target = _pick_target(detections, object_class, color)
        remember_target = getattr(perception, "remember_target", None)
        if target is not None:
            if callable(remember_target):
                remember_target(frame, target)
        elif target_acquired:
            recover_target = getattr(perception, "recover_target", None)
            if callable(recover_target):
                target = recover_target(frame, object_class, color)

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
                            distance, t0):
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
                            distance, t0):
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
            distance, t0):
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
                     t0: float) -> bool:
    if distance > config.FOUND_DISTANCE_M:
        return False

    skills.stop()
    pose = skills.get_robot_pose()
    frame = skills.get_camera_frame()
    detections = perception.detect(frame)
    target = _pick_target(detections, object_class, color)
    if target is None:
        recover_target = getattr(perception, "recover_target", None)
        if callable(recover_target):
            target = recover_target(frame, object_class, color)
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
