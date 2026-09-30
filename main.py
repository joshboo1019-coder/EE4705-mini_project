"""
main.py — ALL. The only file that wires the real (or mock) implementations
together. Nobody develops against this file day-to-day; you only touch it
during integration, and each flag below can be flipped independently so
integration happens incrementally rather than all-at-once the night before
the deadline.
"""

import argparse
from core.schema import CommandQueue
from dialogue.executor import CommandExecutor
from dialogue import chat_interface

# Flip these to False -> True one at a time as each student's real module
# becomes ready. Everything else in the codebase is unaffected by the flip.
USE_REAL_SKILLS = False
USE_REAL_PERCEPTION = False


def build_skills():
    if USE_REAL_SKILLS:
        from skills.skills_real import RealSkills
        return RealSkills()
    from skills.skills_mock import MockSkills
    return MockSkills()


def build_perception():
    if USE_REAL_PERCEPTION:
        from perception.perception_real import RealPerception
        return RealPerception()
    from perception.perception_mock import MockPerception
    return MockPerception()


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()

    skills = build_skills()
    perception = build_perception()
    queue = CommandQueue()

    chat_interface.start_chat_thread(queue)

    executor = CommandExecutor(skills, perception, queue)
    executor.run_forever()  # blocks; keep the sim/physics alive in here
    # TODO(Student A): if your platform needs its own physics-stepping loop
    # driven from the main thread (rather than inside skills.move()), that
    # loop belongs here instead of a plain executor.run_forever() call —
    # discuss with B before changing this file.


if __name__ == "__main__":
    main()
