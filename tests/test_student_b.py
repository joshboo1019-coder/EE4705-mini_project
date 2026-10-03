"""
tests/test_student_b.py — STUDENT B OWNS THIS FILE. Part of Task 3 (60%).

Exercise parse -> queue -> executor end-to-end without needing
Student A's MuJoCo sim or Student C's YOLO to exist yet.

    python -m pytest -q tests/test_student_b.py   # offline: fake LLM, no keys
    python tests/test_student_b.py                # live: calls config.LLM_SERVICE

(If ROS's PYTHONPATH is set in your shell, prefix with `env -u PYTHONPATH`.)
"""

import json
import threading
import time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core import config
from core.schema import (
    CommandQueue, MoveCommand, TurnCommand, GotoObjectCommand, StopCommand,
    ChatCommand,
)
from skills.skills_mock import MockSkills
from perception.perception_mock import MockPerception
from dialogue.executor import CommandExecutor
from dialogue import chat_interface, llm_parser

TEST_UTTERANCES = [
    "walk forward for three seconds, then turn back",
    "go to the green chair",
    "fly to the roof",          # should be rejected
    "avancez tout droit",       # non-English, should be rejected
]


# ---------------------------------------------------------------------------
# Offline tests: _call_llm is replaced by a fake, so these need no API key.
# ---------------------------------------------------------------------------

def _actions(*acts):
    return json.dumps({"actions": list(acts)})


MOVE_3S = {"action": "move", "vx": 0.8, "vy": 0.0, "wz": 0.0, "duration": 3.0}
TURN_BACK = {"action": "turn", "angle_deg": 180}


@pytest.fixture
def fake_llm(monkeypatch):
    """Replaces _call_llm with a canned reply; records what it was sent."""
    calls = []
    replies = []

    def fake(user_text, history):
        calls.append((user_text, [dict(m) for m in history]))
        return replies.pop(0)

    monkeypatch.setattr(llm_parser, "_call_llm", fake)
    fake.calls, fake.replies = calls, replies
    return fake


def test_multi_step_command_is_ordered(fake_llm, capsys):
    fake_llm.replies.append(_actions(MOVE_3S, TURN_BACK))
    r = llm_parser.parse_command(TEST_UTTERANCES[0], [])
    assert r.accepted
    assert r.commands == [MoveCommand(0.8, 0.0, 0.0, 3.0), TurnCommand(180.0)]
    assert "[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2" in capsys.readouterr().out


def test_goto_object_normalised(fake_llm):
    fake_llm.replies.append(_actions(
        {"action": "goto_object", "class": " Chair ", "color": "GREEN"}))
    r = llm_parser.parse_command("go to the green chair", [])
    assert r.commands == [GotoObjectCommand("chair", "green")]


def test_goto_object_without_colour_asks_which_one(fake_llm):
    fake_llm.replies.append(_actions(
        {"action": "goto_object", "class": "chair", "color": ""}))
    r = llm_parser.parse_command("go to the chair", [])
    assert r.accepted
    assert r.commands == [ChatCommand("Which chair do you mean? Please tell me its colour.")]


def test_colour_follow_up_sees_the_clarifying_question(fake_llm):
    history, queue = [], CommandQueue()
    fake_llm.replies += [
        _actions({"action": "goto_object", "class": "chair", "color": ""}),
        _actions({"action": "goto_object", "class": "chair", "color": "green"}),
    ]
    chat_interface.handle_utterance("go to the chair", history, queue)
    chat_interface.handle_utterance("the green one", history, queue)

    text, seen = fake_llm.calls[1]
    assert text == "the green one"
    assert seen[0] == {"role": "user", "content": "go to the chair"}
    assert json.loads(seen[1]["content"]) == {"actions": [
        {"action": "chat", "reply": "Which chair do you mean? Please tell me its colour."}]}
    assert queue.pop(timeout=0) == ChatCommand(
        "Which chair do you mean? Please tell me its colour.")
    assert queue.pop(timeout=0) == GotoObjectCommand("chair", "green")


def test_model_rejection_is_passed_through(fake_llm, capsys):
    fake_llm.replies.append('{"rejected": true, "reason": "impossible:fly"}')
    r = llm_parser.parse_command("fly to the roof", [])
    assert not r.accepted and r.reject_reason == "impossible:fly"
    assert "[CMD] rejected reason=impossible:fly" in capsys.readouterr().out


@pytest.mark.parametrize("text,reason", [
    ("", "empty"),
    ("   ", "empty"),
    ("向前走三秒", "non-English"),
    ("иди вперёд", "non-English"),
])
def test_precheck_rejects_without_calling_llm(fake_llm, text, reason):
    r = llm_parser.parse_command(text, [])
    assert not r.accepted and r.reject_reason == reason
    assert fake_llm.calls == []


@pytest.mark.parametrize("raw,reason", [
    ("not json", "malformed_json"),
    ('{"foo": 1}', "invalid_field:actions"),
    ('{"actions": []}', "empty_actions"),
    (_actions({"action": "dance"}), "unknown_action:dance"),
    (_actions({**MOVE_3S, "vx": 2.0}), "invalid_field:vx"),
    (_actions({**MOVE_3S, "duration": 0}), "invalid_field:duration"),
    (_actions({**MOVE_3S, "duration": 999}), "invalid_field:duration"),
    (_actions({**MOVE_3S, "vy": -1.5}), "invalid_field:vy"),
    (_actions({**MOVE_3S, "wz": 1.01}), "invalid_field:wz"),
    (_actions({**MOVE_3S, "duration": 30.5}), "invalid_field:duration"),
    ('{"actions": [{"action": "turn", "angle_deg": Infinity}]}', "invalid_field:angle_deg"),
    (_actions({"action": "turn", "angle_deg": "left"}), "invalid_field:angle_deg"),
    (_actions({"action": "move", "vx": 0.5, "vy": 0, "wz": 0}), "invalid_field:duration"),
    (_actions({"action": "goto_object", "color": "red"}), "invalid_field:class"),
    (_actions("move"), "invalid_field:action"),
    (_actions({**MOVE_3S, "vx": "fast"}), "invalid_field:vx"),
    (_actions({**MOVE_3S, "vx": True}), "invalid_field:vx"),
    (_actions({"action": "move", "vx": 0.5}), "invalid_field:vy"),
    (_actions({"action": "goto_object", "class": "unicorn", "color": ""}),
     "unknown_class:unicorn"),
    (_actions({"action": "chat", "reply": ""}), "invalid_field:reply"),
])
def test_invalid_llm_output_is_rejected(fake_llm, raw, reason):
    fake_llm.replies.append(raw)
    r = llm_parser.parse_command("walk", [])
    assert not r.accepted and r.reject_reason == reason


def test_one_bad_action_rejects_the_whole_batch(fake_llm):
    fake_llm.replies.append(_actions(MOVE_3S, {"action": "turn"}))
    r = llm_parser.parse_command("walk then turn", [])
    assert not r.accepted and r.commands == []


def test_markdown_fences_are_tolerated(fake_llm):
    fake_llm.replies.append("```json\n" + _actions({"action": "stop"}) + "\n```")
    assert llm_parser.parse_command("stop", []).commands == [StopCommand()]


@pytest.mark.parametrize("raw,want", [
    ('{"action": "stop"}', [StopCommand()]),
    (json.dumps(MOVE_3S), [MoveCommand(0.8, 0.0, 0.0, 3.0)]),
])
def test_bare_action_object_is_a_one_element_list(fake_llm, raw, want):
    fake_llm.replies.append(raw)
    r = llm_parser.parse_command("halt!", [])
    assert r.accepted and r.commands == want


def test_llm_failure_becomes_rejection(monkeypatch):
    def boom(user_text, history):
        raise TimeoutError("slow")
    monkeypatch.setattr(llm_parser, "_call_llm", boom)
    r = llm_parser.parse_command("walk forward", [])
    assert not r.accepted and r.reject_reason == "llm_error:TimeoutError"


def test_chat_loop_survives_llm_errors(monkeypatch, capsys):
    """An LLM/network/auth failure is a printed rejection, and the loop
    goes on to read (and parse) the next line."""
    calls = []

    def flaky(user_text, history):
        calls.append(user_text)
        if len(calls) == 1:
            raise ConnectionError("down")
        return _actions({"action": "stop"})

    lines = iter(["walk forward", "stop"])

    def fake_input(prompt=""):
        try:
            return next(lines)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr(llm_parser, "_call_llm", flaky)
    monkeypatch.setattr("builtins.input", fake_input)
    queue = CommandQueue()
    chat_interface._chat_loop(queue)
    out = capsys.readouterr().out
    assert "[CMD] rejected reason=llm_error:ConnectionError" in out
    assert calls == ["walk forward", "stop"]
    assert isinstance(queue.pop(timeout=0), StopCommand)


def test_chat_runs_in_its_own_thread(monkeypatch):
    import threading
    started = threading.Event()
    release = threading.Event()

    def blocking_input(prompt=""):
        started.set()
        release.wait(5)   # the chat thread sits in input() ...
        raise EOFError

    monkeypatch.setattr("builtins.input", blocking_input)
    t = chat_interface.start_chat_thread(CommandQueue())
    assert started.wait(2)
    # ... while the caller (the executor's thread) is free to carry on.
    assert t is not threading.current_thread() and t.daemon and t.is_alive()
    release.set()
    t.join(2)
    assert not t.is_alive()


def test_unknown_service_is_reported(monkeypatch):
    monkeypatch.setattr(config, "LLM_SERVICE", "no-such-llm")
    r = llm_parser.parse_command("walk forward", [])
    assert not r.accepted and r.reject_reason == "llm_error:ValueError"


def test_history_entry_round_trips():
    r = llm_parser._to_parse_result(_actions(MOVE_3S, TURN_BACK))
    assert llm_parser._to_parse_result(llm_parser.history_entry(r)).commands == r.commands


def test_chat_history_supports_follow_ups(fake_llm, monkeypatch):
    monkeypatch.setattr(config, "LLM_HISTORY_TURNS", 2)
    history, queue = [], CommandQueue()
    fake_llm.replies += [
        _actions(MOVE_3S),
        '{"rejected": true, "reason": "impossible:fly"}',
        _actions({**MOVE_3S, "vx": 0.4}),
    ]
    chat_interface.handle_utterance("walk forward for three seconds", history, queue)
    chat_interface.handle_utterance("fly", history, queue)
    chat_interface.handle_utterance("do that again, but slower", history, queue)

    # The LLM sees only PREVIOUS turns, never the current utterance twice.
    text, seen = fake_llm.calls[2]
    assert text == "do that again, but slower"
    assert [m["content"] for m in seen if m["role"] == "user"] == [
        "walk forward for three seconds", "fly"]
    # The assistant turn holds the accepted actions themselves.
    assert json.loads(seen[1]["content"]) == {"actions": [MOVE_3S]}
    assert json.loads(seen[3]["content"]) == {"rejected": True,
                                              "reason": "impossible:fly"}
    # Trimmed to LLM_HISTORY_TURNS exchanges.
    assert len(history) == 4 and history[0]["content"] == "fly"
    # Only the two accepted moves were queued.
    assert [queue.pop(timeout=0).vx for _ in range(2)] == [0.8, 0.4]
    assert queue.empty()


class _FailingMoveSkills(MockSkills):
    """move() always raises; records stop() and turn() calls."""

    def __init__(self):
        super().__init__()
        self.stops, self.turns = 0, []
        self.turned = threading.Event()

    def move(self, vx, vy, wz, duration):
        raise RuntimeError("joint limit exceeded")

    def turn(self, angle_deg):
        self.turns.append(angle_deg)
        self.turned.set()

    def stop(self):
        self.stops += 1


def _run_executor_in_background(executor):
    threading.Thread(target=executor.run_forever, kwargs={"poll_timeout": 0.01},
                     daemon=True).start()


def test_failing_skill_skips_the_batch_and_the_loop_keeps_going(capsys):
    skills, queue = _FailingMoveSkills(), CommandQueue()
    executor = CommandExecutor(skills, MockPerception(), queue)
    queue.push_many([MoveCommand(0.8, 0.0, 0.0, 3.0), TurnCommand(180.0)])
    _run_executor_in_background(executor)
    time.sleep(0.2)
    queue.push_many([TurnCommand(-90.0)])            # a later batch

    assert skills.turned.wait(timeout=2.0)
    assert skills.turns == [-90.0]                   # 2/2 of the failed batch was skipped
    assert skills.stops == 1
    out = capsys.readouterr().out
    assert "[EXEC] action=1/2 failed reason=RuntimeError: joint limit exceeded" in out
    assert "[DONE] actions=0" in out
    assert "[EXEC] action=1/1 turn angle=-90.0 deg" in out


def test_goto_object_error_does_not_kill_the_loop(capsys):
    def goto_boom(object_class, color, skills, perception):
        raise KeyError(f"{color}_{object_class}")

    skills, queue = _FailingMoveSkills(), CommandQueue()
    executor = CommandExecutor(skills, MockPerception(), queue, goto_object_fn=goto_boom)
    queue.push_many([TurnCommand(90.0), GotoObjectCommand("chair", "purple"), TurnCommand(45.0)])
    _run_executor_in_background(executor)
    time.sleep(0.2)
    queue.push_many([TurnCommand(-90.0)])

    deadline = time.time() + 2.0
    while len(skills.turns) < 2 and time.time() < deadline:
        time.sleep(0.01)
    assert skills.turns == [90.0, -90.0]
    assert skills.stops == 1
    out = capsys.readouterr().out
    assert "[EXEC] action=2/3 failed reason=KeyError: 'purple_chair'" in out
    assert "[DONE] actions=1" in out


def test_end_to_end_on_mocks(fake_llm, capsys):
    fake_llm.replies += [
        _actions(MOVE_3S, TURN_BACK),
        _actions({"action": "chat", "reply": "I can walk and turn."}),
    ]
    queue = CommandQueue()
    executor = CommandExecutor(MockSkills(), MockPerception(), queue)
    for text in ["walk forward for three seconds, then turn back",
                 "what can you do?"]:
        chat_interface.handle_utterance(text, [], queue)
        executor._run_batch_starting_with(queue.pop())
    out = capsys.readouterr().out
    assert "[EXEC] action=1/2 move" in out and "[EXEC] action=2/2 turn" in out
    assert "[DONE] actions=2" in out
    assert "Robot: I can walk and turn." in out


# ---------------------------------------------------------------------------
# Live smoke test against the real config.LLM_SERVICE.
# ---------------------------------------------------------------------------

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
