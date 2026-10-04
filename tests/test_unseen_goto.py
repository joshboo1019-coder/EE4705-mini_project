# Owner: Student B (Task 3)
"""
tests/test_unseen_goto.py -- [B] fix/unseen-goto.

A reject whose ONLY reason is "object not seen" (v5.1 still produced it once
`look` answers were in the history) becomes the plain goto it was, with
"[PLAN] note=object not seen yet -> search"; every other reject (unsafe,
non-English, out-of-range, injection, mixed commands, unknown classes) is
unchanged. Fake LLM, no network, still exactly one LLM call per utterance.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dialogue import llm_parser  # noqa: E402

NOTE = "[PLAN] note=object not seen yet -> search"
LOOK_HISTORY = [
    {"role": "user", "content": "what can you see?"},
    {"role": "assistant", "content": '{"actions": [{"action": "look", "question": "what can you see?"}]}'},
    {"role": "user", "content": "is there a chair in front of you?"},
    {"role": "assistant", "content": '{"actions": [{"action": "look", "question": "is there a chair in front of you?"}]}'},
]
STATE = "STATE: near the start | last command: look | camera has seen (first to last): orange sports ball, green chair"


@pytest.fixture
def llm(monkeypatch):
    calls = []

    def install(reply):
        def fake(user_text, history, snapshot=None):
            calls.append(user_text)
            return json.dumps(reply)
        monkeypatch.setattr(llm_parser, "_call_llm", fake)
        return calls
    return install


def test_look_then_goto_an_unseen_object_executes_as_a_search(llm, capsys):
    calls = llm({"rejected": True, "reason": "impossible:object_not_seen"})
    r = llm_parser.parse_command("go to the red chair", LOOK_HISTORY, snapshot=STATE)
    out = capsys.readouterr().out
    assert r.accepted and len(calls) == 1
    assert [(c.object_class, c.color) for c in r.commands] == [("chair", "red")]
    assert NOTE in out and "[CMD] actions=goto_object(class=chair, color=red) n=1" in out
    assert "[CMD] rejected" not in out
    assert out.index(NOTE) < out.index("[CMD] actions=")


def test_multi_goal_with_an_unseen_object(llm, capsys):
    llm({"rejected": True, "reason": "object_not_seen"})
    r = llm_parser.parse_command("go to the red chair, then the orange ball", LOOK_HISTORY, snapshot=STATE)
    assert r.accepted
    assert [(c.object_class, c.color) for c in r.commands] == [("chair", "red"), ("sports ball", "orange")]


@pytest.mark.parametrize("text,reply", [
    # safety rejects are never converted, even for a goto utterance
    ("go to the red chair", {"rejected": True, "reason": "unsafe:collision"}),
    ("go to the red chair", {"rejected": True, "reason": "non-English"}),
    ("go to the red chair", {"rejected": True, "reason": "out_of_range:distance"}),
    ("go to the red chair", {"rejected": True, "reason": "prompt_injection"}),
    # object_not_seen, but the utterance is more than a goto / no known target
    ("go to the red chair and jump down the stairs", {"rejected": True, "reason": "impossible:object_not_seen"}),
    ("go to the purple unicorn", {"rejected": True, "reason": "impossible:object_not_seen"}),
    ("go to the chair", {"rejected": True, "reason": "impossible:object_not_seen"}),
    ("is there a red chair?", {"rejected": True, "reason": "impossible:object_not_seen"}),
])
def test_other_rejects_are_unchanged(llm, capsys, text, reply):
    llm(reply)
    r = llm_parser.parse_command(text, LOOK_HISTORY, snapshot=STATE)
    out = capsys.readouterr().out
    assert not r.accepted and r.reject_reason == reply["reason"].replace(" ", "_")
    assert NOTE not in out and f"[CMD] rejected reason={r.reject_reason}" in out


def test_non_english_is_rejected_before_the_llm(llm, capsys):
    calls = llm({"actions": [{"action": "goto_object", "class": "chair", "color": "red"}]})
    r = llm_parser.parse_command("去红色的椅子", LOOK_HISTORY, snapshot=STATE)
    assert not r.accepted and r.reject_reason == "non-English" and calls == []
    assert NOTE not in capsys.readouterr().out
