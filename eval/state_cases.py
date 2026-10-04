"""
eval/state_cases.py — STUDENT B OWNS THIS FILE. Task 3 upgrade evaluation.

HELD-OUT "set S": goto commands whose object is NOT in the STATE line.

Written and committed BEFORE the prompt fix it evaluates (v5.1, branch
iter/state-unseen). Bug seen on the real sim (qwen-flash, prompt v5): after
two `look` commands the STATE snapshot listed what YOLO had seen ("camera
has seen (first to last): orange sports ball, green chair, ...") without
the red chair, and "go to the red chair, then the orange ball" came back
as {"rejected": true, "reason": "impossible:object_not_seen"}. goto_object
searches for its target by itself, so an object missing from STATE is
never a reason to reject or to ask.

Same format and mechanism as eval/hard_cases.py: (id, category, setup,
utterance, checker), and STATES[id] = the canned robot state (YOLO
detections in first-seen order) that dialogue/state.py renders into the
snapshot line sent in front of the utterance (task3_eval.render_state).

Categories:
  unseen   colour + class goto whose object is NOT in STATE (single goto,
           multi-goal, until_see + goto)          -> goto_object(s) accepted
  seen     the same utterances with the object IN STATE (controls) -> goto
  must_not still ambiguous / impossible with an unseen object -> no motion

No utterance is a phrasing from eval/hard_cases.py, the Standard CASES in
eval/task3_eval.py, or a prompt few-shot example (tests/test_upgrade_b.py).
Do not edit after the v5.1 runs except to fix a checker bug (list it here).
"""

from eval.hard_cases import all_turns, any_of, gt, no_motion, rej, seq, until

BALL = "sports ball"

STATE_CASES = [
    # --- unseen: the object is not in the STATE seen list -> goto anyway ---
    ("S-U1", "unseen", [], "walk over to the red chair, then on to the orange ball",
     seq(gt("chair", "red"), gt(BALL, "orange"))),
    ("S-U2", "unseen", [], "please make your way to the yellow stop sign",
     seq(gt("stop sign", "yellow"))),
    ("S-U3", "unseen", [], "find me the blue chair",
     seq(gt("chair", "blue"))),
    ("S-U4", "unseen", [], "track down the red stop sign and walk up to it",
     any_of(seq(gt("stop sign", "red")),
            seq(until("stop sign", "red"), gt("stop sign", "red")))),
    ("S-U5", "unseen", [], "keep rotating left until the yellow ball shows up, then walk over to it",
     seq(until(BALL, "yellow", do=all_turns(+1)), gt(BALL, "yellow"))),
    ("S-U6", "unseen", [], "visit the green chair first, then the red stop sign, and finish at the blue chair",
     seq(gt("chair", "green"), gt("stop sign", "red"), gt("chair", "blue"))),
    ("S-U7", "unseen", [], "now go and stand by the red ball",
     seq(gt(BALL, "red"))),

    # --- seen: controls, same utterance with the object in STATE ---
    ("S-K1", "seen", [], "walk over to the red chair, then on to the orange ball",
     seq(gt("chair", "red"), gt(BALL, "orange"))),
    ("S-K2", "seen", [], "please make your way to the yellow stop sign",
     seq(gt("stop sign", "yellow"))),

    # --- must_not: still ambiguous / impossible -> no motion ---
    ("S-A1", "must_not", [], "go over to that spot", no_motion()),
    ("S-A2", "must_not", [], "swim across to the blue chair", rej()),
]

# Robot-state facts per case (YOLO detections only, first-seen order).
STATES = {
    "S-U1": {"seen": [("orange", BALL), ("green", "chair")]},          # the real-sim bug
    "S-U2": {"seen": [("green", "chair"), ("red", "stop sign")]},
    "S-U3": {"seen": [("red", "stop sign"), ("orange", BALL)]},
    "S-U4": {"seen": []},                                              # "nothing yet"
    "S-U5": {"seen": [("green", "chair"), ("orange", BALL)]},
    "S-U6": {"seen": [("green", "chair"), ("orange", BALL)]},
    "S-U7": {"seen": [("red", "chair")]},                              # red, but another class
    "S-K1": {"seen": [("orange", BALL), ("green", "chair"), ("red", "chair")]},
    "S-K2": {"seen": [("yellow", "stop sign"), ("green", "chair")]},
    "S-A1": {"seen": [("orange", BALL), ("green", "chair")]},
    "S-A2": {"seen": [("green", "chair")]},
}

CATEGORIES = ["unseen", "seen", "must_not"]
