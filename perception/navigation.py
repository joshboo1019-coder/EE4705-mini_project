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
    degrees_turned = 0.0

    while time.time() - t0 < config.APPROACH_TIMEOUT_S:
        frame = skills.get_camera_frame()
        detections = perception.detect(frame)
        target = _pick_target(detections, object_class, color)

        if target is None:
            consecutive_misses += 1
            if consecutive_misses >= config.MAX_MISSES_BEFORE_LOST:
                print("[SEARCH] target not visible, rotating")
                skills.turn(config.SEARCH_TURN_DEG)
                degrees_turned += config.SEARCH_TURN_DEG
                consecutive_misses = 0
                if degrees_turned >= 360.0:
                    print("[MISSION] status=FAIL reason=not_found")
                    return False
            continue

        consecutive_misses = 0

        if not _steer_to_center(target, skills, frame.shape[1]):
            # not centered yet — small turn step and re-detect next loop
            continue

        # Centered: step forward, then check whether a stop-time verification is due.
        skills.move(vx=config.APPROACH_VX, vy=0.0, wz=0.0,
                     duration=config.APPROACH_STEP_S)

        pose = skills.get_robot_pose()
        d = _ground_truth_distance(pose, object_class, color)
        if d <= config.FOUND_DISTANCE_M:
            skills.stop()

            # Require a fresh camera classification at the stopped position.
            pose = skills.get_robot_pose()
            frame = skills.get_camera_frame()
            detections = perception.detect(frame)
            if _pick_target(detections, object_class, color) is None:
                continue

            d = _ground_truth_distance(pose, object_class, color)
            if d > config.FOUND_DISTANCE_M:
                continue

            elapsed = time.time() - t0
            print(f"[FOUND] class={object_class} color={color} "
                  f"t={elapsed:.1f} s d={d:.2f} m")
            print("[MISSION] status=SUCCESS")
            return True

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
    """Proportional steering on wz from the bbox-center pixel offset.
    Returns True once roughly centered within config.CENTER_TOLERANCE_PX.

    duration=0.3s below, not the 0.1s this used to be: SkillsAPI.move()
    resets the command back to (0, 0, 0) the instant its duration
    elapses (see its own docstring), and the walking policy actively
    damps out residual angular velocity once commanded back to a
    neutral cmd -- so a very short wz pulse barely has time to turn the
    robot at all before it's immediately cancelled. This was found from
    an actual failed run: over 300+ consecutive _steer_to_center calls
    at duration=0.1, final yaw only ever matched the SEARCH phase's own
    30deg-per-turn rotations almost exactly (nothing accumulated once
    steering started), and the bbox offset from center never closed --
    just noise-jittered in place call after call, which is what a pulse
    too short to do anything looks like, not a detection or camera
    problem. 0.3s is a starting point, not a verified-optimal value --
    if it's still not converging, try increasing it further (or
    decreasing it if it now overshoots/oscillates around the tolerance
    band instead of approaching it) and re-check against a real run's
    log the same way this was diagnosed."""
    x1, _, x2, _ = detection.bbox
    bbox_center_x = (x1 + x2) / 2.0
    offset_x = bbox_center_x - frame_width / 2.0

    if abs(offset_x) <= config.CENTER_TOLERANCE_PX:
        return True

    # Positive wz turns left, so a target right of center requires a right turn.
    wz = max(-0.5, min(0.5, -offset_x / (frame_width / 2.0)))
    skills.move(vx=0.0, vy=0.0, wz=wz, duration=0.3)
    return False


def _ground_truth_distance(pose: RobotPose, object_class: str, color: str) -> float:
    """Planar trunk-to-object distance for the [FOUND] check and log only."""
    key = f"{color}_{object_class}"
    x_obj, y_obj = config.OBJECT_POSITIONS[key]
    x_base, y_base = pose.x, pose.y
    return ((x_base - x_obj) ** 2 + (y_base - y_obj) ** 2) ** 0.5
