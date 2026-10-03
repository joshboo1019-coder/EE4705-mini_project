"""
eval/mock_main.py — STUDENT B OWNS THIS FILE. Task 3 smoke test.

Runs main.py's full pipeline (chat thread + executor) on
MockSkills / MockPerception without editing main.py's integration flags.
Thin wrapper around `main.py --mock` (any other CLI args are ignored).

    env -u PYTHONPATH .venv/bin/python eval/mock_main.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402

if __name__ == "__main__":
    sys.argv = sys.argv[:1] + ["--mock"]
    main.main()
