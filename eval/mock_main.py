"""
eval/mock_main.py — STUDENT B OWNS THIS FILE. Task 3 smoke test.

Runs main.py's full pipeline (chat thread + executor) on
MockSkills / MockPerception without editing main.py's integration flags.

    env -u PYTHONPATH .venv/bin/python eval/mock_main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402

main.USE_REAL_SKILLS = main.USE_REAL_PERCEPTION = False

if __name__ == "__main__":
    sys.argv = sys.argv[:1]
    main.main()
