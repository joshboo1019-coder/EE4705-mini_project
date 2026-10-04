# Owner: ALL (shared tooling, written by Student A)
"""
tools/check_status.py — quick "what's actually implemented" sweep.

Run from the project root:

    python tools/check_status.py

What it does:
  1. Scans each task's own files for the two tell-tale signs of an
     unfinished stub: a literal `raise NotImplementedError` and a
     `# TODO(Student X)` comment.
  2. Runs the one contract check that needs no external dependencies —
     tests/test_student_a.py against the mock — and reports pass/fail.

What it deliberately does NOT do:
  - It does not run anything that needs mujoco, an LLM API key, a real
    camera frame, or YOLO weights (tests/test_student_b.py,
    tests/test_student_c.py, `python -m skills.skills_real`, etc. still
    need to be run by hand — see the printed reminder at the bottom).
  - It cannot tell you whether your LOGIC is correct — only whether a
    stub/TODO marker is still sitting in the file. A file with no stub
    marker can still be buggy; that's what the real tests and a human
    reviewer are for.

This is a fast first pass before you push or before a teammate reads
your code — not a replacement for tests/ or the handout's grading
checklist.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# One entry per task; edit this list if files move or new ones are added.
TASKS = {
    "Task 2 - Student A  (skills/, assets/scenes/)": [
        "skills/skills_real.py",
        "assets/scenes/custom_scene.xml",
    ],
    "Task 3 - Student B  (dialogue/)": [
        "dialogue/llm_parser.py",
        "dialogue/executor.py",
        "dialogue/chat_interface.py",
    ],
    "Task 4 - Student C  (perception/)": [
        "perception/perception_real.py",
        "perception/navigation.py",
    ],
}

STUB_PATTERNS = [
    re.compile(r"raise\s+NotImplementedError"),
    re.compile(r"#\s*TODO"),
]


def scan_file(path: Path):
    """Returns a list of 'line N: <text>' hits, or ['MISSING'] if the
    file doesn't exist, or [] if it looks clean."""
    if not path.exists():
        return ["MISSING"]
    text = path.read_text(errors="replace")
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pat in STUB_PATTERNS:
            if pat.search(line):
                hits.append(f"line {lineno}: {line.strip()}")
    return hits


def main() -> int:
    print("=" * 70)
    print("MiniLab 1.3 - quick status sweep")
    print("=" * 70)

    found_stub_or_missing = False

    for task, files in TASKS.items():
        print(f"\n{task}")
        for rel in files:
            path = ROOT / rel
            hits = scan_file(path)
            if hits == ["MISSING"]:
                print(f"  [MISSING] {rel}")
                found_stub_or_missing = True
            elif hits:
                print(f"  [STUB]    {rel}")
                for h in hits:
                    print(f"              {h}")
                found_stub_or_missing = True
            else:
                print(f"  [OK]      {rel}  (no NotImplementedError / TODO found)")

    print("\n" + "-" * 70)
    print("Running the dependency-light contract check "
          "(tests/test_student_a.py, against the mock)...")
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests" / "test_student_a.py")],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        for line in result.stdout.strip().splitlines():
            print(f"  {line}")
        if result.returncode != 0:
            found_stub_or_missing = True
            for line in result.stderr.strip().splitlines():
                print(f"  {line}")
    except Exception as e:
        print(f"  could not run: {e}")
        found_stub_or_missing = True

    print("\n" + "=" * 70)
    if found_stub_or_missing:
        print("Result: at least one stub / TODO / missing file / failing "
              "check found above.")
    else:
        print("Result: no NotImplementedError/TODO stubs found in the "
              "scanned files, and the mock-based contract check passed.")
    print()
    print("Reminder - this sweep can't run everything, so still run by hand:")
    print("  python -m pytest -q tests/               # architecture + handoff")
    print("  python tests/test_student_b.py            # needs an LLM API key")
    print("  python tests/test_student_c.py            # needs a test image")
    print("  python -m skills.skills_real               # needs mujoco + ONNX policy")
    print("=" * 70)

    return 1 if found_stub_or_missing else 0


if __name__ == "__main__":
    sys.exit(main())
