# Owner: ALL (backbone)
"""[ALL] Static check: no simulator ground truth in perception or dialogue logic.

The handout allows ground truth (core/config.OBJECT_POSITIONS, the sim's
body positions) only for logging/evaluation. This test parses the decision
code with `ast` (nothing is imported or run) and fails on any reference to

  * `OBJECT_POSITIONS` (as a name, an attribute, or `getattr(x, "OBJECT_POSITIONS")`),
  * `.xpos` (MuJoCo body positions) on anything,
  * `._data` / `._model` on a skills object (an expression naming `skills`),

outside the allowed logging helpers listed in ALLOWED. In navigation.py the
only allowed helper is `_ground_truth_distance` (the `[FOUND]` / `[RANGE]`
log distance), and its return value may only be printed. Nothing is allowed
in perception_real.py or dialogue/.
"""
import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKED = (["perception/navigation.py", "perception/perception_real.py"]
           + sorted(str(p.relative_to(REPO)) for p in (REPO / "dialogue").glob("*.py")))
ALLOWED = {"perception/navigation.py": {"_ground_truth_distance"}}

GT_NAMES = {"OBJECT_POSITIONS"}
GT_ANY_ATTRS = {"xpos"}
GT_SKILLS_ATTRS = {"_data", "_model"}


def _mentions_skills(node):
    """True if an expression chain (a.b.c, a[0].b, f().b) names `skills`."""
    for sub in ast.walk(node):
        name = (sub.id if isinstance(sub, ast.Name)
                else sub.attr if isinstance(sub, ast.Attribute) else "")
        if "skills" in name.lower():
            return True
    return False


def _gt_access(node):
    """Return a description if `node` is a ground-truth access, else None."""
    if isinstance(node, ast.Name) and node.id in GT_NAMES:
        return node.id
    if isinstance(node, ast.Attribute):
        if node.attr in GT_NAMES or node.attr in GT_ANY_ATTRS:
            return "." + node.attr
        if node.attr in GT_SKILLS_ATTRS and _mentions_skills(node.value):
            return "skills ." + node.attr
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in {"getattr", "hasattr", "setattr"} and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)):
        attr = node.args[1].value
        if attr in GT_NAMES or attr in GT_ANY_ATTRS:
            return f"getattr(..., {attr!r})"
        if attr in GT_SKILLS_ATTRS and _mentions_skills(node.args[0]):
            return f"getattr(skills, {attr!r})"
    return None


def violations(source, allowed=frozenset(), filename="<src>"):
    """[(line, what, enclosing function)] for disallowed ground-truth accesses."""
    found = []

    def visit(node, funcs):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            funcs = funcs + (node.name,)
        what = _gt_access(node)
        if what and not (set(funcs) & set(allowed)):
            found.append((node.lineno, what, ".".join(funcs) or "<module>"))
        for child in ast.iter_child_nodes(node):
            visit(child, funcs)

    visit(ast.parse(source, filename=filename), ())
    return found


def _log_only_violations(source, helper):
    """Uses of `x = helper(...)` results anywhere but inside a print(...) call."""
    tree = ast.parse(source)
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}

    def inside_print(node):
        while node in parents:
            node = parents[node]
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "print"):
                return True
        return False

    bad = []
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper:
                parent = parents.get(node)
                if isinstance(parent, ast.Assign) and all(isinstance(t, ast.Name) for t in parent.targets):
                    names |= {t.id for t in parent.targets}
                elif not inside_print(node):
                    bad.append((node.lineno, f"{helper}(...) result used outside print", func.name))
        for node in ast.walk(func):
            if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                    and node.id in names and not inside_print(node)):
                bad.append((node.lineno, f"{node.id} (from {helper}) used outside print", func.name))
    return bad


@pytest.mark.parametrize("rel", CHECKED)
def test_no_ground_truth_outside_logging_helpers(rel):
    src = (REPO / rel).read_text()
    bad = violations(src, ALLOWED.get(rel, frozenset()), rel)
    assert not bad, f"{rel}: ground truth referenced outside {sorted(ALLOWED.get(rel, ()))}: {bad}"


def test_ground_truth_distance_is_only_logged():
    src = (REPO / "perception/navigation.py").read_text()
    assert "def _ground_truth_distance" in src
    assert not _log_only_violations(src, "_ground_truth_distance")


def test_checker_catches_violations():
    src = (
        "from core import config\n"
        "def steer(skills, data):\n"
        "    a = config.OBJECT_POSITIONS['red_chair']\n"
        "    b = skills._data.xpos[3]\n"
        "    c = self._skills._model\n"
        "    d = getattr(skills, '_data')\n"
        "    e = data.xpos\n"
        "    return OBJECT_POSITIONS\n"
        "def _ground_truth_distance(pose):\n"
        "    return config.OBJECT_POSITIONS['x']\n"
        "class Speech:\n"
        "    def load(self):\n"
        "        self._model = object()\n"
    )
    lines = sorted({line for line, _, _ in violations(src, {"_ground_truth_distance"})})
    assert lines == [3, 4, 5, 6, 7, 8]
    log_src = (
        "def f(pose):\n"
        "    d = _ground_truth_distance(pose)\n"
        "    print(f'd={d:.2f}')\n"
        "    if d < 1.0:\n"
        "        return True\n"
    )
    assert [line for line, _, _ in _log_only_violations(log_src, "_ground_truth_distance")] == [4]
