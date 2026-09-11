"""
Student C: run this to test goto_object()'s search/steer/approach state
machine without needing Student A's MuJoCo sim running.

    python tests/test_navigation_with_mock.py

MockPerception returns "not found" for the first few calls (exercises the
[SEARCH] branch) and then a detection (exercises steering + [FOUND]).
Implement _steer_to_center() in navigation.py before this will pass.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.skills_mock import MockSkills
from perception.perception_mock import MockPerception
from perception import navigation


def main():
    skills = MockSkills()
    perception = MockPerception(misses_before_found=2)
    ok = navigation.goto_object("chair", "green", skills, perception)
    print("\nResult:", "SUCCESS" if ok else "FAIL")


if __name__ == "__main__":
    main()
