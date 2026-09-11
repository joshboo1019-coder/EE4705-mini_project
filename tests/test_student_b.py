"""
Student B: run this to exercise parse -> queue -> executor end-to-end
without needing Student A's MuJoCo sim or Student C's YOLO to exist yet.

    python tests/test_parser_with_mock.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.schema import CommandQueue
from skills.skills_mock import MockSkills
from perception.perception_mock import MockPerception
from dialogue.executor import CommandExecutor
from dialogue import llm_parser

TEST_UTTERANCES = [
    "walk forward for three seconds, then turn back",
    "go to the green chair",
    "fly to the roof",          # should be rejected
    "avancez tout droit",       # non-English, should be rejected
]


def main():
    skills = MockSkills()
    perception = MockPerception()
    queue = CommandQueue()
    executor = CommandExecutor(skills, perception, queue)

    for text in TEST_UTTERANCES:
        print(f"\nUser: {text}")
        result = llm_parser.parse_command(text, history=[])
        if result.accepted:
            queue.push_many(result.commands)
            # drain synchronously for this smoke test
            executor._run_batch_starting_with(queue.pop())


if __name__ == "__main__":
    main()
