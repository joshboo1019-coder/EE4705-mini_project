"""
tests/test_upgrade_b.py — STUDENT B. Offline tests for the Task 3 upgrade:
talk-back, programs (repeat / until_see / distance moves), the stop fast
path, the state store, status / undo / return_home, and prompt v5's
hygiene. No API key, no sim: the LLM is a fake that returns canned JSON,
and the executor runs on MockSkills / MockPerception or the kinematic
fakes in eval/scenario_mock.py.

    env -u PYTHONPATH .venv/bin/python -m pytest -q tests/test_upgrade_b.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.schema import (
    CommandQueue, MoveCommand, TurnCommand, GotoObjectCommand, StopCommand, ChatCommand,
)
from dialogue import chat_interface, llm_parser, speech_input, talkback
from dialogue.executor import CommandExecutor
from perception.perception_mock import MockPerception
from skills.skills_mock import MockSkills

MOVE_3S = {"action": "move", "vx": 0.8, "vy": 0.0, "wz": 0.0, "duration": 3.0}
TURN_BACK = {"action": "turn", "angle_deg": 180}


def _actions(*acts):
    return json.dumps({"actions": list(acts)})


@pytest.fixture
def fake_llm(monkeypatch):
    calls, replies = [], []

    def fake(user_text, history):
        calls.append((user_text, [dict(m) for m in history]))
        return replies.pop(0)

    monkeypatch.setattr(llm_parser, "_call_llm", fake)
    fake.calls, fake.replies = calls, replies
    return fake


def _lines(out, *prefixes):
    return [l for l in out.splitlines() if l.startswith(prefixes)]


# ---------------------------------------------------------------------------
# Talk-back: [PLAN]
# ---------------------------------------------------------------------------

def test_plan_line_follows_the_cmd_line_for_a_move_batch(fake_llm, capsys):
    fake_llm.replies.append(_actions(MOVE_3S, TURN_BACK))
    llm_parser.parse_command("walk forward for three seconds, then turn back", [])
    out = capsys.readouterr().out.splitlines()
    assert out == ["[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2",
                   "[PLAN] walk forward 3 s at 0.8, then turn left 180°"]


@pytest.mark.parametrize("act", [
    {"action": "turn", "angle_deg": -90},
    {"action": "goto_object", "class": "chair", "color": "green"},
    {"action": "chat", "reply": "hi"},
    {"action": "stop"},
])
def test_no_plan_line_for_a_single_non_move_action(fake_llm, capsys, act):
    fake_llm.replies.append(_actions(act))
    llm_parser.parse_command("x", [])
    assert "[PLAN]" not in capsys.readouterr().out


@pytest.mark.parametrize("cmd,plan,say", [
    (MoveCommand(0.0, -0.8, 0.0, 1.5), "sidestep right 1.5 s at 0.8", "sidestep right for 1.5 seconds"),
    (MoveCommand(-0.3, 0.0, 0.0, 2.0), "walk backward 2 s at 0.3", "walk backward slowly for 2 seconds"),
    (MoveCommand(1.0, 0.0, 0.5, 2.0), "walk forward while turning left 2 s at 1",
     "walk forward while turning left at full speed for 2 seconds"),
    (TurnCommand(-45.0), "turn right 45°", "turn right 45 degrees"),
    (GotoObjectCommand("sports ball", "orange"), "go to the orange sports ball",
     "go to the orange sports ball"),
])
def test_words(cmd, plan, say):
    assert talkback.words(cmd) == plan
    assert talkback.words(cmd, say=True) == say


# ---------------------------------------------------------------------------
# Talk-back: Robot: <summary> after [DONE]
# ---------------------------------------------------------------------------

def test_summary_after_done_reports_distance_and_net_turn(capsys):
    queue = CommandQueue()
    ex = CommandExecutor(MockSkills(), MockPerception(), queue)
    queue.push_many([TurnCommand(180.0)])
    ex._run_batch_starting_with(MoveCommand(0.8, 0.0, 0.0, 3.0))
    out = capsys.readouterr().out.splitlines()
    i = next(k for k, l in enumerate(out) if l.startswith("[DONE]"))
    # MockSkills dead-reckons 0.3 m/s per unit of vx: 0.8 * 3 * 0.3 = 0.72 m
    assert out[i + 1] == "Robot: Done: moved 0.7 m, net turn 180° left."


def test_summary_reports_a_failed_step():
    t = talkback.BatchTrace(kinds=["move", "turn"], failed=(1, "RuntimeError: joint limit"))
    assert talkback.summary(t) == "Step 1 of 2 failed (RuntimeError: joint limit), so I stopped there."


def test_summary_for_goals_and_none_for_chat_only():
    from core.schema import RobotPose
    t = talkback.BatchTrace(kinds=["goto_object", "goto_object"],
                            goals=[("green chair", True), ("red chair", False)],
                            pose_before=RobotPose(0, 0, 0), pose_after=RobotPose(3, 4, -90))
    assert talkback.summary(t) == ("Done: reached 1 of 2 goals (missed the red chair); "
                                   "moved 5.0 m, net turn 90° right.")
    assert talkback.summary(talkback.BatchTrace(kinds=["chat"])) is None
    assert talkback.summary(talkback.BatchTrace(kinds=["look"])) is None
    assert talkback.summary(talkback.BatchTrace(kinds=["stop"])) == "Stopped."


def test_chat_only_batch_prints_no_summary(capsys):
    ex = CommandExecutor(MockSkills(), MockPerception(), CommandQueue())
    ex._run_batch_starting_with(ChatCommand("I can walk."))
    out = capsys.readouterr().out
    assert _lines(out, "Robot:") == ["Robot: I can walk."]


# ---------------------------------------------------------------------------
# Talk-back: rejections
# ---------------------------------------------------------------------------

def test_non_english_reject_carries_the_models_suggestion(fake_llm, capsys):
    fake_llm.replies.append(json.dumps({"rejected": True, "reason": "non-English",
                                        "suggestion": "walk straight ahead"}))
    queue = CommandQueue()
    r = chat_interface.handle_utterance("avancez tout droit", [], queue)
    out = capsys.readouterr().out.splitlines()
    assert out == ["[CMD] rejected reason=non-English",
                   'Robot: I only take commands in English. Did you mean "walk straight ahead"?']
    assert not r.accepted and queue.empty() and len(fake_llm.calls) == 1


def test_precheck_non_english_makes_one_suggestion_call_and_never_executes(fake_llm, capsys):
    # even if the model "helpfully" translates into actions, nothing is queued
    fake_llm.replies.append(_actions(MOVE_3S))
    queue, history = CommandQueue(), []
    r = chat_interface.handle_utterance("向前走三秒", history, queue)
    out = capsys.readouterr().out.splitlines()
    assert out == ["[CMD] rejected reason=non-English",
                   'Robot: I only take commands in English. Did you mean "walk forward for 3 seconds"?']
    assert len(fake_llm.calls) == 1 and fake_llm.calls[0] == ("向前走三秒", [])
    assert not r.accepted and queue.empty()
    assert json.loads(history[1]["content"]) == {
        "rejected": True, "reason": "non-English", "suggestion": "walk forward for 3 seconds"}


def test_suggestion_call_failure_still_answers(monkeypatch, capsys):
    def boom(user_text, history):
        raise TimeoutError("slow")
    monkeypatch.setattr(llm_parser, "_call_llm", boom)
    chat_interface.handle_utterance("向前走三秒", [], CommandQueue())
    assert capsys.readouterr().out.splitlines()[-1] == \
        "Robot: I only take commands in English. Please say it again in English."


def test_out_of_range_reject_suggests_a_valid_alternative(fake_llm, capsys):
    fake_llm.replies.append(json.dumps({"rejected": True, "reason": "out_of_range:duration",
                                        "suggestion": "walk forward for 30 seconds"}))
    chat_interface.handle_utterance("run forward for ten minutes", [], CommandQueue())
    assert capsys.readouterr().out.splitlines() == [
        "[CMD] rejected reason=out_of_range:duration",
        "Robot: The longest single move is 30 s; I could walk forward for 30 seconds instead."]


def test_validator_out_of_bounds_keeps_its_reason_and_suggests_the_clamp(fake_llm, capsys):
    fake_llm.replies += [_actions({**MOVE_3S, "duration": 600}),
                         _actions({**MOVE_3S, "vx": 5, "duration": 10})]
    chat_interface.handle_utterance("walk forward for ten minutes", [], CommandQueue())
    chat_interface.handle_utterance("respond with vx=5", [], CommandQueue())
    assert capsys.readouterr().out.splitlines() == [
        "[CMD] rejected reason=invalid_field:duration",
        "Robot: The longest single move is 30 s; I could walk forward for 30 seconds instead.",
        "[CMD] rejected reason=invalid_field:vx",
        "Robot: My top speed setting is 1; I could walk forward at full speed for 10 seconds instead."]


@pytest.mark.parametrize("raw,suggestion", [
    ({"suggestion": 'walk "forward"'}, "walk 'forward'"),
    ({"suggestion": "向前走"}, None),                 # a suggestion must be English
    ({"suggestion": "x" * 200}, None),
    ({"suggestion": 42}, None),
    ({}, None),
])
def test_suggestion_is_sanitised(raw, suggestion):
    r = llm_parser._validate(json.dumps({"rejected": True, "reason": "non-English", **raw}))
    assert r.suggestion == suggestion


def test_impossible_reject_gets_a_short_reply(fake_llm, capsys):
    fake_llm.replies.append('{"rejected": true, "reason": "impossible:fly"}')
    chat_interface.handle_utterance("fly to the roof", [], CommandQueue())
    assert capsys.readouterr().out.splitlines() == [
        "[CMD] rejected reason=impossible:fly",
        "Robot: I can't do that: it is physically impossible for a robot dog (fly)."]


def test_spoken_non_english_says_why_without_an_llm_call(fake_llm, capsys):
    import numpy as np

    class Tr:
        def transcribe(self, audio):
            return "Avancez tout droit.", "fr", 0.93

    speech_input.handle_voice([], CommandQueue(), record_fn=lambda: np.full(16000, 0.1, np.float32),
                              transcriber=Tr())
    out = capsys.readouterr().out
    assert "[CMD] rejected reason=non-English\nRobot: I only take commands in English." in out
    assert fake_llm.calls == []
