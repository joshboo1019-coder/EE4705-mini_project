"""
tests/test_handoff.py — BACKBONE (ALL). Full-pipeline integration check.

Where test_student_a/b/c.py each test one person's logic in isolation,
this test exercises the one place all three meet: main.py's own
build_skills() / build_perception() wiring, feeding a real CommandQueue
and CommandExecutor. With USE_REAL_SKILLS / USE_REAL_PERCEPTION left at
their defaults (False), this should always pass — it's the regression
check that catches "the integration point itself is broken", separate
from any one student's own logic.

Run:
    python -m pytest -q tests/test_handoff.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
from core.schema import CommandQueue, MoveCommand, TurnCommand


def test_main_wires_mocks_by_default():
    assert main.USE_REAL_SKILLS is False
    assert main.USE_REAL_PERCEPTION is False
    from skills.skills_mock import MockSkills
    from perception.perception_mock import MockPerception
    assert isinstance(main.build_skills(), MockSkills)
    assert isinstance(main.build_perception(), MockPerception)


def test_executor_runs_a_batch_through_mains_own_wiring():
    from dialogue.executor import CommandExecutor

    skills = main.build_skills()
    perception = main.build_perception()
    queue = CommandQueue()
    executor = CommandExecutor(skills, perception, queue)

    queue.push_many([
        MoveCommand(vx=0.8, vy=0.0, wz=0.0, duration=1.0),
        TurnCommand(angle_deg=180.0),
    ])
    executor._run_batch_starting_with(queue.pop())  # should not raise


if __name__ == "__main__":
    test_main_wires_mocks_by_default()
    test_executor_runs_a_batch_through_mains_own_wiring()
    print("Handoff check passed: main.py's own wiring runs end to end on mocks.")
