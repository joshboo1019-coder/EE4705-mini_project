# Owner: backbone (ALL)
"""Architectural check (AST-based; not a security sandbox).

The one rule that keeps Students A, B and C independent: `dialogue/`
(Student B — the parser, executor, chat loop) must depend only on
`core.interfaces`, never import `skills.skills_real` or
`perception.perception_real` directly. `main.py` is the sole, intentional
exception — it is where the real-vs-mock choice is made — so it is
excluded from this check on purpose.

Run:
    python -m pytest -q tests/test_architecture.py
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHECKED_DIRS = ("dialogue",)
FORBIDDEN_MODULES = ("skills.skills_real", "perception.perception_real")


def _violations_in(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == m or alias.name.startswith(m + ".") for m in FORBIDDEN_MODULES):
                    out.append(f"{path}:{node.lineno} imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if any(mod == m or mod.startswith(m + ".") for m in FORBIDDEN_MODULES):
                out.append(f"{path}:{node.lineno} imports from {mod}")
    return out


def test_dialogue_never_imports_real_implementations():
    violations: list[str] = []
    for dirname in CHECKED_DIRS:
        for path in (ROOT / dirname).rglob("*.py"):
            violations.extend(_violations_in(path))
    assert violations == [], (
        "dialogue/ must only depend on core.interfaces (SkillsAPI / "
        "PerceptionAPI), never on a real implementation directly — that "
        "coupling is exactly what breaks parallel development:\n"
        + "\n".join(violations)
    )


def test_main_is_the_one_intentional_exception():
    """main.py IS allowed to import both real modules — that's its job.
    This documents the exception and doubles as a check that the AST scan
    itself actually flags the pattern it's supposed to."""
    main_src = (ROOT / "main.py").read_text()
    assert "skills.skills_real" in main_src
    assert "perception.perception_real" in main_src


def test_check_actually_detects_violations(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("from skills.skills_real import RealSkills\n")
    assert _violations_in(bad)
    bad.write_text("import perception.perception_real\n")
    assert _violations_in(bad)
    ok = tmp_path / "ok.py"
    ok.write_text("from core.interfaces import SkillsAPI\nimport core.schema\n")
    assert not _violations_in(ok)
