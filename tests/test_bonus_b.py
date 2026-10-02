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
