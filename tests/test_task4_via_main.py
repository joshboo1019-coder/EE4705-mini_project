# Owner: ALL (backbone)
# Change contributed by Student B (assist), pending review by Student C and the group
"""
tests/test_task4_via_main.py — Student B (assist), pending review by Student C
and the group. `main.py --scenario N` (assist/task4-via-main): Task 4 runs
through main.py's own pipeline (typed command -> [CMD] -> executor ->
navigation.goto_object), with Student C's scenario layouts. No sim here.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import main
from core import config
from perception import scenarios


@pytest.fixture
def restore_config():
    saved = dict(config.OBJECT_POSITIONS)
    flags = (main.USE_REAL_SKILLS, main.USE_REAL_PERCEPTION)
    yield
    config.OBJECT_POSITIONS.clear()
    config.OBJECT_POSITIONS.update(saved)
    main.USE_REAL_SKILLS, main.USE_REAL_PERCEPTION = flags


def test_scenario_with_mocks_applies_layout_but_writes_no_scene(restore_config, capsys):
    main.USE_REAL_SKILLS = main.USE_REAL_PERCEPTION = False
    scenario, scene = main.load_scenario("3")
    assert scenario.name == "chairs_three_colors" and scene is None
    assert config.OBJECT_POSITIONS["blue_chair"] == (-5.0, 0.0)
    assert "=== Scenario 3: chairs_three_colors ===" in capsys.readouterr().out


def test_scenario_with_real_skills_writes_its_scene(restore_config, capsys):
    main.USE_REAL_SKILLS = True
    scenario, scene = main.load_scenario("absent_target")
    assert scenario.idx == 10
    assert Path(scene).is_file() and Path(scene).name == "scenario_10_absent_target.xml"
    assert config.OBJECT_POSITIONS["blue_chair"] == (99.0, 99.0)   # absent target
    assert "[SCENARIO] temporary scene written to" in capsys.readouterr().out


def test_build_skills_passes_the_scenario_scene(monkeypatch, restore_config):
    seen = {}

    class FakeRealSkills:
        def __init__(self, **kw):
            seen.update(kw)

    import skills
    monkeypatch.setitem(sys.modules, "skills.skills_real",
                        type(sys)("skills.skills_real"))
    sys.modules["skills.skills_real"].RealSkills = FakeRealSkills
    main.USE_REAL_SKILLS = True
    main.build_skills(gui=True, scene_path=Path("/tmp/x.xml"))
    assert seen == {"gui": True, "native_viewer": False, "scene_path": "/tmp/x.xml"}
    seen.clear()
    main.build_skills()
    assert "scene_path" not in seen                    # default scene unchanged


def test_every_scenario_target_parses_as_a_goto(restore_config):
    """Every scenario target is reachable by a typed goto: the parser
    validator accepts the class/colour the LLM would emit."""
    from dialogue import llm_parser
    import json
    for s in scenarios.SCENARIOS:
        for key in s.keys:
            color, cls = key.split("_", 1)
            raw = json.dumps({"actions": [{"action": "goto_object", "class": cls, "color": color}]})
            r = llm_parser._to_parse_result(raw)
            assert r.accepted and r.commands[0].object_class == cls
