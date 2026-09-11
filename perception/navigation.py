"""
navigation.py — STUDENT C OWNS THIS FILE (other half of Task 4, 60% w/ perception).

goto_object() implements the search/steer/approach behavior and is called
by the Task 3 executor whenever a GotoObjectCommand is popped. It depends
ONLY on SkillsAPI and PerceptionAPI (never on skills_real / perception_real
directly), so you can develop and unit-test it entirely against
skills_mock.MockSkills before Student A's simulation exists:

    python tests/test_navigation_with_mock.py

Ground-truth object positions (config.OBJECT_POSITIONS, filled in by
Student A during Task 2 scene building) are used ONLY to compute the
distance for the [FOUND] log line — never to steer the robot.
"""

import time
from core.interfaces import SkillsAPI, PerceptionAPI
from core.schema import RobotPose
from core import config


def goto_object(object_class: str, color: str,
                 skills: SkillsAPI, perception: PerceptionAPI) -> bool:
    """Runs the full search -> steer -> approach -> stop behavior.
    Returns True iff [MISSION] status=SUCCESS was printed."""
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

        if not _steer_to_center(target, skills):
            # not centered yet — small turn step and re-detect next loop
            continue

        # centered: step forward, then re-check distance/found condition
        skills.move(vx=config.APPROACH_VX, vy=0.0, wz=0.0,
                     duration=config.APPROACH_STEP_S)

        pose = skills.get_robot_pose()
        d = _ground_truth_distance(pose, object_class, color)
        if d <= config.FOUND_DISTANCE_M:
            elapsed = time.time() - t0
            print(f"[FOUND] class={object_class} color={color} "
                  f"t={elapsed:.1f} s d={d:.2f} m")
            print("[MISSION] status=SUCCESS")
            skills.stop()
            return True

    print("[MISSION] status=FAIL reason=timeout")
    skills.stop()
    return False


def _pick_target(detections, object_class: str, color: str):
    for d in detections:
        if d.class_name == object_class and d.color == color:
            return d
    return None


def _steer_to_center(detection, skills: SkillsAPI) -> bool:
    """Proportional steering on wz from the bbox-center pixel offset.
    Returns True once roughly centered within config.CENTER_TOLERANCE_PX."""
    # TODO(Student C):
    #   1. compute bbox center x, compare to frame width / 2
    #   2. if |offset| > tolerance: skills.move(vx=0, vy=0, wz=k*offset, duration=short)
    #      and return False
    #   3. else return True
    raise NotImplementedError


def _ground_truth_distance(pose: RobotPose, object_class: str, color: str) -> float:
    """For [FOUND] logging / evaluation only — never used to steer."""
    key = f"{color}_{object_class}"
    ox, oy = config.OBJECT_POSITIONS[key]
    return ((pose.x - ox) ** 2 + (pose.y - oy) ** 2) ** 0.5
