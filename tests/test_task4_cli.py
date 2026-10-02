from perception import scenarios
from perception.task4_cli import _read_scenario, parse_search_command


def test_parse_search_command_accepts_common_action_phrases():
    phrases = (
        "go to the red stop sign",
        "approach the red stop sign",
        "move to the red stop sign",
        "move closer to the red stop sign",
        "could you please navigate towards a red stop sign?",
        "I'd like you to look for the red stop sign.",
    )

    for phrase in phrases:
        assert parse_search_command(phrase) == {
            "class": "stop sign",
            "color": "red",
        }


def test_parse_search_command_requires_a_configured_colored_target():
    assert parse_search_command("approach the stop sign") is None
    assert parse_search_command("approach the purple stop sign") is None
    assert parse_search_command("turn left") is None


def test_read_scenario_accepts_number_or_case_insensitive_name(monkeypatch):
    answers = iter(("invalid", "CHAIRS_THREE_COLORS"))
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    scenario = _read_scenario()

    assert scenario is scenarios.SCENARIOS[2]


def test_build_scene_xml_writes_to_the_requested_temporary_directory(tmp_path):
    scene_path = scenarios.build_scene_xml(scenarios.SCENARIOS[0], tmp_path)

    assert scene_path.parent == tmp_path
    assert scene_path.is_file()
