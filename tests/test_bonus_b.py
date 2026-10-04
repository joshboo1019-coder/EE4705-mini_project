# Owner: Student B (Task 3 + bonuses)
"""
tests/test_bonus_b.py — STUDENT B. Offline tests for the bonus features
(speech input). No microphone, model download or API key needed: the
recorder, transcriber and LLM are all fakes.

    env -u PYTHONPATH .venv/bin/python -m pytest -q tests/test_bonus_b.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest

from core.schema import CommandQueue, MoveCommand, TurnCommand
from dialogue import chat_interface, llm_parser, speech_input

MOVE_3S = {"action": "move", "vx": 0.8, "vy": 0.0, "wz": 0.0, "duration": 3.0}
TURN_BACK = {"action": "turn", "angle_deg": 180}


@pytest.fixture
def fake_llm(monkeypatch):
    calls, replies = [], []

    def fake(user_text, history):
        calls.append((user_text, [dict(m) for m in history]))
        return replies.pop(0)

    monkeypatch.setattr(llm_parser, "_call_llm", fake)
    fake.calls, fake.replies = calls, replies
    return fake


class FakeTranscriber:
    def __init__(self, text, lang="en", prob=0.98):
        self.result = (text, lang, prob)
        self.calls = 0

    def transcribe(self, audio):
        self.calls += 1
        return self.result


def _one_second_of_audio():
    return np.full(16000, 0.1, dtype=np.float32)


def test_english_speech_goes_through_the_typed_path(fake_llm, capsys):
    fake_llm.replies.append(json.dumps({"actions": [MOVE_3S, TURN_BACK]}))
    history, queue = [], CommandQueue()
    tr = FakeTranscriber("Walk forward for three seconds, then turn back.")
    r = speech_input.handle_voice(history, queue, record_fn=_one_second_of_audio, transcriber=tr)

    assert r.accepted
    assert fake_llm.calls[0][0] == "Walk forward for three seconds, then turn back."
    assert [queue.pop(timeout=0), queue.pop(timeout=0)] == [
        MoveCommand(0.8, 0.0, 0.0, 3.0), TurnCommand(180.0)]
    assert history[0] == {"role": "user",
                          "content": "Walk forward for three seconds, then turn back."}
    out = capsys.readouterr().out
    assert '[STT] text="Walk forward for three seconds, then turn back." lang=en p=0.98 t=' in out
    assert "[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2" in out


def test_non_english_speech_is_rejected_before_the_llm(fake_llm, capsys):
    history, queue = [], CommandQueue()
    tr = FakeTranscriber("Avancez tout droit.", lang="fr", prob=0.93)
    r = speech_input.handle_voice(history, queue, record_fn=_one_second_of_audio, transcriber=tr)

    assert not r.accepted and r.reject_reason == "non-English"
    assert fake_llm.calls == [] and queue.empty()
    assert history[0]["content"] == "Avancez tout droit."
    out = capsys.readouterr().out
    assert '[STT] text="Avancez tout droit." lang=fr p=0.93' in out
    assert "[CMD] rejected reason=non-English" in out


def test_unsure_language_id_falls_through_to_the_llm(fake_llm):
    # Short English commands sometimes come back as another language with
    # low confidence; those go to the LLM, which can still reject them.
    fake_llm.replies.append(json.dumps({"actions": [{"action": "stop"}]}))
    tr = FakeTranscriber("Stop.", lang="nl", prob=0.31)
    r = speech_input.handle_voice([], CommandQueue(), record_fn=_one_second_of_audio,
                                  transcriber=tr)
    assert r.accepted and len(fake_llm.calls) == 1


def test_empty_audio_skips_transcription_and_llm(fake_llm, capsys):
    tr = FakeTranscriber("should not be used")
    history = []
    r = speech_input.handle_voice(history, CommandQueue(),
                                  record_fn=lambda: np.zeros(0, np.float32), transcriber=tr)
    assert not r.accepted and r.reject_reason == "empty"
    assert tr.calls == 0 and fake_llm.calls == [] and history == []
    out = capsys.readouterr().out
    assert '[STT] text="" lang=- p=0.00' in out and "[CMD] rejected reason=empty" in out


def test_blank_transcript_is_rejected_as_empty(fake_llm):
    r = speech_input.handle_voice([], CommandQueue(), record_fn=_one_second_of_audio,
                                  transcriber=FakeTranscriber(""))
    assert not r.accepted and r.reject_reason == "empty" and fake_llm.calls == []


def _frames(levels_dbfs, frame_s=speech_input.FRAME_S):
    n = int(speech_input.SAMPLE_RATE * frame_s)
    for db in levels_dbfs:
        amp = 32768 * 10 ** (db / 20)
        yield np.full(n, amp, dtype=np.int16)   # constant-level test signal, not speech


def test_recorder_stops_after_a_second_of_silence(capsys):
    per_s = int(round(1 / speech_input.FRAME_S))
    levels = [0] * (per_s // 2) + [-20] * per_s + [-45] * (3 * per_s)   # pop, "speech", silence
    audio = speech_input.record(frames=_frames(levels))
    assert 1.9 < len(audio) / speech_input.SAMPLE_RATE < 2.2   # 1 s loud + 1 s silence
    assert "[MIC] captured 2." in capsys.readouterr().out


def test_recorder_returns_empty_when_nothing_is_said():
    per_s = int(round(1 / speech_input.FRAME_S))
    audio = speech_input.record(frames=_frames([-45] * (8 * per_s)))
    assert audio.size == 0


def test_chat_loop_routes_v_to_push_to_talk(monkeypatch):
    seen = []
    inputs = iter(["v", "walk forward"])

    def fake_input(prompt=""):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(speech_input, "handle_voice", lambda h, q: seen.append("voice"))
    monkeypatch.setattr(chat_interface, "handle_utterance",
                        lambda text, h, q: seen.append(("typed", text)))
    chat_interface._chat_loop(CommandQueue())
    assert seen == ["voice", ("typed", "walk forward")]


# ---------------------------------------------------------------------------
# Visual QA (look -> VLM)
# ---------------------------------------------------------------------------

from types import SimpleNamespace

from core import config
from dialogue import vlm
from dialogue.commands import LookCommand
from dialogue.executor import CommandExecutor
from perception.perception_mock import MockPerception
from skills.skills_mock import MockSkills


def test_look_action_is_parsed(fake_llm, capsys):
    fake_llm.replies.append(json.dumps(
        {"actions": [{"action": "look", "question": " what can you see? "}]}))
    r = llm_parser.parse_command("what can you see?", [])
    assert r.accepted and r.commands == [LookCommand("what can you see?")]
    assert '[CMD] actions=look("what can you see?") n=1' in capsys.readouterr().out
    # it round-trips through the history like the other actions
    assert llm_parser._to_parse_result(llm_parser.history_entry(r)).commands == r.commands


@pytest.mark.parametrize("action,reason", [
    ({"action": "look"}, "invalid_field:question"),
    ({"action": "look", "question": "   "}, "invalid_field:question"),
    ({"action": "look", "question": 42}, "invalid_field:question"),
    ({"action": "look", "question": "x" * 301}, "invalid_field:question"),
])
def test_bad_look_is_rejected(fake_llm, action, reason):
    fake_llm.replies.append(json.dumps({"actions": [action]}))
    r = llm_parser.parse_command("what can you see?", [])
    assert not r.accepted and r.reject_reason == reason


class FakeVLMClient:
    """Stands in for the OpenAI-compatible client; records the request."""

    def __init__(self, answer="I see a red stop sign.", fail=None):
        self.requests, self.answer, self.fail = [], answer, fail
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        if self.fail:
            raise self.fail
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.answer))],
            usage=SimpleNamespace(prompt_tokens=400, completion_tokens=9))


def test_vlm_sends_the_frame_and_question(monkeypatch):
    monkeypatch.setattr(config, "VLM_SERVICE", "qwen3-vl-flash")
    client = FakeVLMClient()
    frame = np.zeros((480, 640, 3), np.uint8)
    ans = vlm.ask(frame, "what can you see?", client=client)

    req = client.requests[0]
    assert req["model"] == "qwen3-vl-flash"
    assert req["messages"][0] == {"role": "system", "content": vlm.SYSTEM_PROMPT}
    text, image = req["messages"][1]["content"]
    assert text == {"type": "text", "text": "what can you see?"}
    assert image["image_url"]["url"].startswith("data:image/png;base64,")
    assert (ans.answer, ans.model, ans.tokens_in, ans.tokens_out) == (
        "I see a red stop sign.", "qwen3-vl-flash", 400, 9)


def test_vlm_empty_answer_is_an_error():
    with pytest.raises(ValueError):
        vlm.ask(np.zeros((4, 4, 3), np.uint8), "what can you see?",
                service="qwen3-vl-flash", client=FakeVLMClient(answer="  "))


def _look_executor(tmp_path, vlm_fn):
    saved = []

    def save(frame):
        saved.append(frame.shape)
        return tmp_path / "frame.png"

    queue = CommandQueue()
    ex = CommandExecutor(MockSkills(), MockPerception(misses_before_found=0), queue,
                         vlm_fn=vlm_fn, save_frame_fn=save)
    return ex, saved


def test_look_runs_yolo_and_the_vlm_on_the_same_frame(tmp_path, capsys):
    seen = []

    def fake_vlm(frame, question):
        seen.append((frame.shape, question))
        return vlm.VLMAnswer("A green chair is ahead.", "qwen3-vl-flash", 0.61, 401, 7)

    ex, saved = _look_executor(tmp_path, fake_vlm)
    ex._run_batch_starting_with(LookCommand("what can you see?"))
    out = capsys.readouterr().out
    assert saved == [seen[0][0]] and seen[0][1] == "what can you see?"
    lines = [l for l in out.splitlines() if l.startswith(("[EXEC]", "[DETECT]", "[VLM]", "Robot:", "[DONE]"))]
    assert lines[0] == '[EXEC] action=1/1 look question="what can you see?"'
    assert lines[1].startswith("[DETECT] class=")            # YOLO (mock) on that frame
    assert lines[2] == f"[VLM] model=qwen3-vl-flash t=0.61 s tokens=401/7 frame={tmp_path / 'frame.png'}"
    assert lines[3] == "Robot: A green chair is ahead."
    assert lines[4].startswith("[DONE] actions=1")


def test_vlm_error_is_caught_and_the_loop_goes_on(tmp_path, capsys):
    import openai

    def boom(frame, question):
        raise openai.APITimeoutError(request=None)

    ex, _ = _look_executor(tmp_path, boom)
    ex._run_batch_starting_with(LookCommand("what can you see?"))
    ex._run_batch_starting_with(TurnCommand(90.0))           # a later batch still runs
    out = capsys.readouterr().out
    assert "[EXEC] action=1/1 failed reason=APITimeoutError" in out
    assert "[DONE] actions=0" in out
    assert "[EXEC] action=1/1 turn angle=90.0 deg" in out and "[DONE] actions=1" in out


# ---------------------------------------------------------------------------
# Part 3: multi-goal missions (executor side; navigation is faked)
# ---------------------------------------------------------------------------

def _mission_executor(results):
    """Executor whose goto_object returns the given results in order."""
    from core.schema import GotoObjectCommand  # noqa: F401
    from dialogue.executor import CommandExecutor
    from perception.perception_mock import MockPerception
    from skills.skills_mock import MockSkills

    calls = []
    it = iter(results)

    def fake_goto(object_class, color, skills, perception):
        calls.append(f"{color} {object_class}")
        return next(it)

    queue = CommandQueue()
    ex = CommandExecutor(MockSkills(), MockPerception(), queue, goto_object_fn=fake_goto)
    return ex, queue, calls


def _run(ex, queue, cmds):
    queue.push_many(cmds[1:])
    ex._run_batch_starting_with(cmds[0])


def test_mission_all_goals_reached(capsys):
    from core.schema import GotoObjectCommand
    ex, queue, calls = _mission_executor([True, True, True])
    _run(ex, queue, [GotoObjectCommand("sports ball", "orange"), GotoObjectCommand("chair", "green"),
                     GotoObjectCommand("chair", "red")])
    out = capsys.readouterr().out
    assert calls == ["orange sports ball", "green chair", "red chair"]
    assert "[GOAL] 1/3 orange sports ball status=REACHED" in out
    assert "[GOAL] 3/3 red chair status=REACHED" in out
    assert "[MULTI] status=SUCCESS reached=3/3 t=" in out
    assert "[DONE] actions=3" in out


def test_mission_skips_a_missed_goal_and_continues(capsys):
    from core.schema import GotoObjectCommand
    ex, queue, calls = _mission_executor([True, False, True])
    _run(ex, queue, [GotoObjectCommand("sports ball", "orange"), GotoObjectCommand("chair", "green"),
                     GotoObjectCommand("chair", "red")])
    out = capsys.readouterr().out
    assert calls == ["orange sports ball", "green chair", "red chair"]   # goal 3 still attempted
    assert "[GOAL] 2/3 green chair status=NOT_REACHED" in out
    assert "[MULTI] status=PARTIAL reached=2/3 missed=green_chair t=" in out


def test_mission_with_no_goal_reached_fails(capsys):
    from core.schema import GotoObjectCommand
    ex, queue, _ = _mission_executor([False, False])
    _run(ex, queue, [GotoObjectCommand("chair", "green"), GotoObjectCommand("chair", "red")])
    assert "[MULTI] status=FAIL reached=0/2 missed=green_chair,red_chair" in capsys.readouterr().out


def test_mission_mixed_with_a_turn(capsys):
    from core.schema import GotoObjectCommand
    ex, queue, calls = _mission_executor([True, True])
    _run(ex, queue, [GotoObjectCommand("chair", "green"), TurnCommand(180.0),
                     GotoObjectCommand("sports ball", "orange")])
    out = capsys.readouterr().out
    assert "[EXEC] action=2/3 turn angle=180.0 deg" in out
    assert "[GOAL] 2/2 orange sports ball status=REACHED" in out
    assert "[MULTI] status=SUCCESS reached=2/2" in out


def test_mission_error_counts_remaining_goals_as_not_attempted(capsys):
    from core.schema import GotoObjectCommand
    from dialogue.executor import CommandExecutor
    from perception.perception_mock import MockPerception
    from skills.skills_mock import MockSkills

    def goto(object_class, color, skills, perception):
        if color == "green":
            raise RuntimeError("camera frame timeout")
        return True

    queue = CommandQueue()
    ex = CommandExecutor(MockSkills(), MockPerception(), queue, goto_object_fn=goto)
    _run(ex, queue, [GotoObjectCommand("sports ball", "orange"), GotoObjectCommand("chair", "green"),
                     GotoObjectCommand("chair", "red")])
    out = capsys.readouterr().out
    assert "[EXEC] action=2/3 failed reason=RuntimeError: camera frame timeout" in out
    assert "[MULTI] status=PARTIAL reached=1/3 not_attempted=2" in out


def test_single_goto_prints_no_mission_lines(capsys):
    from core.schema import GotoObjectCommand
    ex, queue, _ = _mission_executor([True])
    _run(ex, queue, [GotoObjectCommand("chair", "green")])
    out = capsys.readouterr().out
    assert "[GOAL]" not in out and "[MULTI]" not in out


def test_parser_keeps_goal_order():
    raw = json.dumps({"actions": [
        {"action": "goto_object", "class": "chair", "color": "red"},
        {"action": "goto_object", "class": "chair", "color": "green"},
        {"action": "goto_object", "class": "sports ball", "color": "orange"}]})
    r = llm_parser._to_parse_result(raw)
    assert r.accepted
    assert [(c.object_class, c.color) for c in r.commands] == [
        ("chair", "red"), ("chair", "green"), ("sports ball", "orange")]
