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


# ---------------------------------------------------------------------------
# Programs: validator
# ---------------------------------------------------------------------------

from dialogue.commands import DistanceMoveCommand, RepeatCommand, UntilSeeCommand  # noqa: E402
from eval.scenario_mock import KinematicSkills, ScenarioPerception  # noqa: E402

TURN_L = {"action": "turn", "angle_deg": 90}
FWD_1M = {"action": "move", "vx": 0.8, "vy": 0.0, "wz": 0.0, "distance_m": 1.0}
SQUARE = {"action": "repeat", "times": 4, "actions": [FWD_1M, TURN_L]}
SPIN_UNTIL = {"action": "until_see", "class": "sports ball", "color": "orange",
              "do": [{"action": "turn", "angle_deg": 45}], "max_iter": 8}


def _v(*acts):
    return llm_parser._validate(_actions(*acts))


def test_square_is_one_repeat_with_a_closed_loop_leg(capsys):
    r = llm_parser._to_parse_result(_actions(SQUARE))
    assert r.accepted and r.commands == [
        RepeatCommand(4, [DistanceMoveCommand(0.8, 0.0, 0.0, 1.0), TurnCommand(90.0)])]
    assert capsys.readouterr().out.splitlines() == [
        "[CMD] actions=repeat(4x: move(vx=0.8, 1.0 m), turn(90 deg)) n=1",
        "[PLAN] repeat 4x (walk forward 1 m at 0.8, then turn left 90°)"]


def test_until_see_then_goto(capsys):
    r = llm_parser._to_parse_result(_actions(
        SPIN_UNTIL, {"action": "goto_object", "class": "sports ball", "color": "orange"}))
    assert r.commands == [UntilSeeCommand("sports ball", "orange", [TurnCommand(45.0)], 8),
                          GotoObjectCommand("sports ball", "orange")]
    out = capsys.readouterr().out
    assert ("[CMD] actions=until_see(class=sports ball, color=orange, max_iter=8: turn(45 deg)), "
            "goto_object(class=sports ball, color=orange) n=2") in out
    assert ("[PLAN] until I see the orange sports ball, up to 8x (turn left 45°), "
            "then go to the orange sports ball") in out


def test_until_see_defaults_and_any_colour():
    r = _v({"action": "until_see", "class": "Chair", "do": [TURN_L]})
    assert r.commands == [UntilSeeCommand("chair", "", [TurnCommand(90.0)], 8)]


def test_program_round_trips_through_the_history():
    r = _v(SQUARE, SPIN_UNTIL)
    assert llm_parser._validate(llm_parser.history_entry(r)).commands == r.commands


def test_negative_distance_walks_the_other_way():
    r = _v({**FWD_1M, "distance_m": -1.5})
    assert r.commands == [DistanceMoveCommand(0.8, 0.0, 0.0, -1.5)]
    assert talkback.words(r.commands[0]) == "walk backward 1.5 m at 0.8"


@pytest.mark.parametrize("acts,reason", [
    ([{**SQUARE, "times": 9}], "too_many_iterations:9"),
    ([{**SPIN_UNTIL, "max_iter": 20}], "too_many_iterations:20"),
    ([{**SQUARE, "times": 0}], "invalid_field:times"),
    ([{**SQUARE, "times": 2.5}], "invalid_field:times"),
    ([{**SQUARE, "times": True}], "invalid_field:times"),
    ([{**SQUARE, "times": "4"}], "invalid_field:times"),
    ([{"action": "repeat", "actions": [TURN_L]}], "invalid_field:times"),
    ([{**SQUARE, "actions": []}], "invalid_field:actions"),
    ([{**SPIN_UNTIL, "do": "turn"}], "invalid_field:do"),
    ([{**SPIN_UNTIL, "class": "unicorn"}], "unknown_class:unicorn"),
    # depth 3: repeat > repeat > repeat
    ([{"action": "repeat", "times": 2, "actions": [
        {"action": "repeat", "times": 2, "actions": [
            {"action": "repeat", "times": 2, "actions": [TURN_L]}]}]}], "nesting_too_deep"),
    ([{"action": "repeat", "times": 2, "actions": [{"action": "look", "question": "q"}]}],
     "invalid_in_program:look"),
    ([{"action": "repeat", "times": 2, "actions": [{"action": "stop"}]}], "invalid_in_program:stop"),
    ([{"action": "repeat", "times": 2, "actions": [{"action": "dance"}]}], "unknown_action:dance"),
    ([{"action": "repeat", "times": 2, "actions": [{**MOVE_3S, "vx": 3}]}], "invalid_field:vx"),
    # time estimate: 3 x 30 s of moves; 8 x 10 s; turns at 45 deg/s
    ([{**MOVE_3S, "duration": 30}] * 3, "program_too_long:90s"),
    ([{"action": "repeat", "times": 8, "actions": [{**MOVE_3S, "duration": 10}]}], "program_too_long:80s"),
    ([{"action": "turn", "angle_deg": 3600}], "program_too_long:80s"),
    ([{"action": "repeat", "times": 8, "actions": [{**FWD_1M, "distance_m": 8.0}]}],
     "program_too_long:80s"),
    # one distance move must fit in one move's time (30 s at |v|)
    ([{**FWD_1M, "distance_m": 100}], "out_of_range:distance_m"),
    ([{**FWD_1M, "vx": 0.0}], "invalid_field:distance_m"),
    ([{**FWD_1M, "distance_m": 0}], "invalid_field:distance_m"),
    ([{**FWD_1M, "distance_m": "far"}], "invalid_field:distance_m"),
    ([{**FWD_1M, "vx": 4}], "invalid_field:vx"),
])
def test_program_bounds(acts, reason):
    r = _v(*acts)
    assert not r.accepted and r.reject_reason == reason


def test_bounds_are_inclusive():
    assert _v({"action": "repeat", "times": 8, "actions": [{**MOVE_3S, "duration": 7.5}]}).accepted
    assert _v(*[{**MOVE_3S, "duration": 30}] * 2).accepted                   # exactly 60 s
    assert _v({**FWD_1M, "vx": 1.0, "distance_m": 30}).accepted             # exactly 30 s
    assert _v({"action": "repeat", "times": 2, "actions": [
        {"action": "repeat", "times": 2, "actions": [TURN_L]}]}).accepted      # depth 2


def test_goto_and_look_are_not_in_the_time_estimate():
    r = _v(*[{"action": "goto_object", "class": "chair", "color": c} for c in ("red", "green")],
           {"action": "look", "question": "what now?"}, {**MOVE_3S, "duration": 30},
           {**MOVE_3S, "duration": 30})
    assert r.accepted


def test_goto_without_colour_inside_a_program_asks_instead():
    r = _v({"action": "repeat", "times": 2, "actions": [
        {"action": "goto_object", "class": "chair", "color": ""}, TURN_L]})
    assert r.accepted and r.commands == [ChatCommand("Which chair do you mean? Please tell me its colour.")]


def test_out_of_range_program_talkback(fake_llm, capsys):
    fake_llm.replies += [
        _actions({"action": "repeat", "times": 20, "actions": [{**MOVE_3S, "duration": 1}]}),
        _actions({**FWD_1M, "distance_m": 100}),
        _actions(*[{**MOVE_3S, "duration": 30}] * 3)]
    for text in ("walk forward one second, twenty times", "walk 100 m", "walk 90 s in 3 goes"):
        chat_interface.handle_utterance(text, [], CommandQueue())
    assert _lines(capsys.readouterr().out, "Robot:") == [
        "Robot: I can repeat something at most 8 times; I could walk forward for 1 second, "
        "8 times instead.",
        "Robot: The longest single move is 30 s, about 24 m at walking speed; I could walk "
        "forward 24 metres instead.",
        "Robot: One request can take at most 60 s of motion and that one needs about 90 s. "
        "Could you ask for something smaller?"]


# ---------------------------------------------------------------------------
# Programs: interpreter
# ---------------------------------------------------------------------------

def _kin_executor(skills=None, perception=None, **kw):
    skills = skills or KinematicSkills()
    perception = perception or ScenarioPerception(skills, objects=[])
    queue = CommandQueue()
    ex = CommandExecutor(skills, perception, queue, **kw)
    ex.UNTIL_SETTLE_S = 0.0
    return ex, skills, queue


def _run_cmds(ex, queue, cmds):
    queue.push_many(cmds[1:])
    ex._run_batch_starting_with(cmds[0])


def test_square_program_runs_closed_loop_and_comes_back(capsys):
    ex, skills, queue = _kin_executor()
    _run_cmds(ex, queue, _v(SQUARE).commands)
    out = capsys.readouterr().out
    assert out.count("[REPEAT] iteration=") == 4 and "[REPEAT] iteration=4/4" in out
    assert out.count("[EXEC] action=1/1 move vx=0.8 vy=0.0 wz=0.0 distance=1.0 m") == 4
    moves = [l for l in out.splitlines() if l.startswith("[MOVE]")]
    assert len(moves) == 4
    for l in moves:
        err = float(l.split("final_error=")[1].split()[0])
        assert l.startswith("[MOVE] target=1.00 m final_error=") and abs(err) <= 0.05
    p = skills.get_robot_pose()
    assert math.hypot(p.x, p.y) < 0.1 and abs(p.yaw_deg) < 1e-6      # a closed square
    assert "[DONE] actions=1" in out


def test_distance_walk_on_the_slow_mock_still_arrives(capsys):
    ex, _, queue = _kin_executor(skills=MockSkills())      # 0.3 m/s per unit of vx
    ex._run_batch_starting_with(DistanceMoveCommand(0.8, 0.0, 0.0, 1.0))
    l = _lines(capsys.readouterr().out, "[MOVE]")[0]
    assert abs(float(l.split("final_error=")[1].split()[0])) <= 0.05


def test_distance_walk_stops_when_blocked(capsys):
    class Wall(KinematicSkills):
        def move(self, vx, vy, wz, duration):
            self.moves.append(duration)          # commanded, but the robot doesn't move
    ex, skills, _ = _kin_executor(skills=Wall())
    ex._run_batch_starting_with(DistanceMoveCommand(0.8, 0.0, 0.0, 2.0))
    out = capsys.readouterr().out
    assert "[MOVE] target=2.00 m final_error=-2.00 m status=blocked" in out
    assert sum(skills.moves) <= CommandExecutor.DIST_STALL_WINDOW_S + CommandExecutor.DIST_STEP_S


def test_distance_walk_time_cap(capsys):
    class Crawl(KinematicSkills):
        SPEED_PER_UNIT = 0.05                  # makes progress, far too slowly
    ex, skills, _ = _kin_executor(skills=Crawl())
    ex.DIST_STALL_MIN_M = 0.0
    ex._run_batch_starting_with(DistanceMoveCommand(1.0, 0.0, 0.0, 2.0))
    assert "status=timeout" in capsys.readouterr().out
    assert sum(m[3] for m in skills.moves) <= 4 * 2.0 + 2.0 + 1e-6


def test_until_see_turns_until_the_target_is_in_view_then_goes(capsys):
    goto_calls = []
    skills = KinematicSkills()
    # orange ball behind the robot: needs 4 x 45 deg to bring it into the 80 deg view
    per = ScenarioPerception(skills, objects=[("sports ball", "orange", -3.0, 0.0)], quiet=True)
    ex, _, queue = _kin_executor(skills, per,
                                 goto_object_fn=lambda c, col, s, p: goto_calls.append((c, col)) or True)
    _run_cmds(ex, queue, _v(SPIN_UNTIL, {"action": "goto_object", "class": "sports ball",
                                         "color": "orange"}).commands)
    out = capsys.readouterr().out
    assert skills.turns == [45.0] * 4
    assert "[UNTIL] seen class=sports ball color=orange conf=0.80 after 4 iteration(s)" in out
    assert goto_calls == [("sports ball", "orange")]
    assert _lines(out, "Robot:")[-1] == ("Robot: Done: saw the orange sports ball after 4 tries; "
                                         "reached the orange sports ball; net turn 180° left.")


def test_until_see_gives_up_after_max_iter_and_skips_the_rest(capsys):
    goto_calls = []
    ex, skills, queue = _kin_executor(goto_object_fn=lambda *a: goto_calls.append(a) or True)
    cmd = UntilSeeCommand("sports ball", "orange", [TurnCommand(45.0)], 3)
    _run_cmds(ex, queue, [cmd, GotoObjectCommand("sports ball", "orange")])
    out = capsys.readouterr().out
    assert skills.turns == [45.0] * 3 and goto_calls == []
    assert "[UNTIL] not seen after 3 iteration(s)" in out
    assert "[EXEC] until_see target not seen; skipping 1 remaining action(s)" in out
    assert "[DONE] actions=1" in out
    assert ("Robot: I skipped the last 1 step: never saw the orange sports ball (3 tries); "
            "net turn 135° left.") in out


def test_until_see_any_colour_matches_the_class(capsys):
    skills = KinematicSkills()
    per = ScenarioPerception(skills, objects=[("chair", "blue", 2.0, 0.0)], quiet=True)
    ex, _, _ = _kin_executor(skills, per)
    ex._run_batch_starting_with(UntilSeeCommand("chair", "", [TurnCommand(45.0)], 8))
    assert skills.turns == [] and "[UNTIL] seen class=chair color=blue" in capsys.readouterr().out


def test_program_never_calls_the_llm(fake_llm):
    fake_llm.replies.append(_actions(SQUARE))
    queue = CommandQueue()
    ex, skills, _ = _kin_executor()
    ex.queue = queue
    chat_interface.handle_utterance("walk in a square with 1 metre sides", [], queue)
    ex._run_batch_starting_with(queue.pop(timeout=0))
    assert len(fake_llm.calls) == 1 and len(skills.turns) == 4     # fake would raise on a 2nd call


# ---------------------------------------------------------------------------
# Stop fast path (e-stop)
# ---------------------------------------------------------------------------

import math  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402


@pytest.mark.parametrize("text", ["stop", "Stop!", "  HALT. ", "freeze", "stop now",
                                  "Emergency stop!", "abort", "e-stop"])
def test_stop_words(text):
    assert chat_interface.is_stop_word(text)


@pytest.mark.parametrize("text", ["careful, stop there", "stop at the chair", "don't stop",
                                  "stopwatch", "go", ""])
def test_not_stop_words(text):
    assert not chat_interface.is_stop_word(text)


def _background(ex):
    t = threading.Thread(target=ex.run_forever, kwargs={"poll_timeout": 0.01}, daemon=True)
    t.start()
    return t


def _wait(pred, timeout=5.0):
    deadline = time.time() + timeout
    while not pred() and time.time() < deadline:
        time.sleep(0.005)
    return pred()


def test_estop_aborts_a_running_program_from_the_chat_thread(fake_llm, capsys):
    skills = KinematicSkills(sleep_scale=0.2, quiet=True)          # 1 sim-s = 0.2 real s
    queue = CommandQueue()
    ex = CommandExecutor(skills, ScenarioPerception(skills, objects=[]), queue)
    _background(ex)
    fake_llm.replies.append(_actions({"action": "repeat", "times": 8, "actions": [
        {**MOVE_3S, "duration": 1.0}, {"action": "turn", "angle_deg": 30}]}))
    history = []
    chat_interface.handle_utterance("patrol", history, queue)
    assert _wait(lambda: len(skills.moves) >= 2)
    r = chat_interface.handle_utterance("Stop!", history, queue)
    assert r.accepted and r.commands == [StopCommand()]
    assert _wait(lambda: not ex._busy)
    n_moves = len(skills.moves)
    time.sleep(0.3)
    out = capsys.readouterr().out
    assert len(skills.moves) == n_moves < 8                         # nothing new started
    assert skills.stops >= 1 and queue.empty()
    assert len(fake_llm.calls) == 1                                 # "Stop!" never reached the LLM
    est = [l for l in out.splitlines() if l.startswith("[ESTOP]")]
    assert len(est) == 1 and est[0].startswith("[ESTOP] latency=") and est[0].endswith(" ms")
    assert float(est[0].split("=")[1].split()[0]) < 50.0
    assert "aborted reason=emergency_stop" in out
    assert "Robot: Emergency stop: I halted during step 1 of 1" in out
    assert json.loads(history[-1]["content"]) == {"actions": [{"action": "stop"}]}
    # a later command runs normally: the flag is per batch, never "stuck"
    fake_llm.replies.append(_actions({"action": "turn", "angle_deg": -90}))
    chat_interface.handle_utterance("turn right", history, queue)
    assert _wait(lambda: skills.turns and skills.turns[-1] == -90)


def test_estop_interrupts_goto_object_at_its_next_motion_call(fake_llm, capsys):
    skills = KinematicSkills(sleep_scale=0.2, quiet=True)
    started = threading.Event()

    def endless_search(object_class, color, sk, perception):
        started.set()
        while True:                                  # a search that would never end
            sk.turn(30.0)

    queue = CommandQueue()
    ex = CommandExecutor(skills, ScenarioPerception(skills, objects=[]), queue,
                         goto_object_fn=endless_search)
    _background(ex)
    queue.push_many([GotoObjectCommand("chair", "purple")])
    assert started.wait(2)
    chat_interface.handle_utterance("halt", [], queue)
    assert _wait(lambda: not ex._busy)
    assert "[EXEC] action=1/1 aborted reason=emergency_stop" in capsys.readouterr().out
    assert fake_llm.calls == []


def test_estop_when_idle_just_stops(fake_llm, capsys):
    skills = KinematicSkills(quiet=True)
    queue = CommandQueue()
    CommandExecutor(skills, MockPerception(), queue)
    queue.push_many([TurnCommand(90.0)])          # queued, not yet popped: cleared
    chat_interface.handle_utterance("freeze", [], queue)
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("[ESTOP] latency=") and out[1] == "Robot: Stopped."
    assert skills.stops == 1 and queue.empty() and fake_llm.calls == []


def test_stopish_phrases_still_go_through_the_llm(fake_llm):
    queue = CommandQueue()
    CommandExecutor(KinematicSkills(quiet=True), MockPerception(), queue)
    fake_llm.replies.append(_actions({"action": "stop"}))
    r = chat_interface.handle_utterance("careful, stop there", [], queue)
    assert len(fake_llm.calls) == 1 and r.commands == [StopCommand()]
    assert isinstance(queue.pop(timeout=0), StopCommand)


def test_no_fast_path_without_a_bound_executor(fake_llm):
    fake_llm.replies.append(_actions({"action": "stop"}))
    chat_interface.handle_utterance("stop", [], CommandQueue())
    assert len(fake_llm.calls) == 1
