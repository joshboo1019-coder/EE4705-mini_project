"""
eval/noise_cases.py — STUDENT B OWNS THIS FILE. Task 3 upgrade evaluation.

FROZEN HELD-OUT set "N" (noise vs. non-English), 24 cases.

Why it exists: prompt v5 added "an instruction that mixes in words or
numbers from another language is non-English", and on the Hard set
(eval/hard_cases.py) the cheap models then rejected typo-laden ENGLISH as
non-English (qwen-flash noise 8/8 with v4 -> 4/8 with v5). The Hard set's
noise and codeswitch categories have now been looked at, so they cannot
validate a fix. This set was written and committed BEFORE any change to the
v5 language rule, and must not be edited afterwards except to fix a bug in
a checker (list any such fix at the bottom of this docstring). A prompt
must never be tuned on these cases or use them as few-shot examples.

Composition (all expected outcomes in the v5 action vocabulary):

* noise (14): clearly English instructions with typos, transposed letters,
  speech-recognition homophones (incl. numbers heard as other words), dropped
  conjunctions, missing spaces, abbreviations, fillers, run-on text, shouting.
  Expected: the intended action(s), executed.
* foreign (5): a whole instruction in another language written in Latin
  script (French, Spanish, German, Malay, Indonesian).
  Expected: rejected as non-English, nothing executed.
* codeswitch (5): an English instruction with a CONTENT word (direction,
  number, object, verb) from another language (Chinese, French, Spanish,
  Malay, German). Expected: rejected as non-English, nothing executed.

The must-reject checker is stricter than the Hard set's rej(): the reason
must name the language (matches /english|language/i), not just any reject.
The precheck (dialogue/llm_parser.precheck) rejects none of these 24 on its
own (every utterance is mostly ASCII letters), so the LLM decides each one.

Novelty, checked mechanically before this file was committed (the same
check runs as tests/test_upgrade_b.py::test_noise_set_is_novel): after
lower-casing, dropping punctuation and collapsing whitespace, no utterance
here equals any utterance or setup turn of eval/hard_cases.HARD_CASES or
eval/task3_eval.CASES, or any few-shot example user line of prompts v1-v5,
and none occurs as a substring of any of those prompts. Closest neighbour
by difflib ratio (normalised text): 0.93, N-E14 "walk forward for ate
seconds" vs. task3 B1 "walk forward for three seconds" (same template; the
homophone is the test); every other case is <= 0.88. The codeswitch cases
share their PATTERN with the Hard codeswitch cases (that is the skill under
test) but no phrasing.

Checker fixes after freezing: none.
"""

import re

from eval.hard_cases import FORMAT_FAILURES, _desc, go, gt, seq, stp, tn

def non_english():
    """Rejected (content reason, not a format failure) AS non-English:
    the reason must mention English / language. Nothing executed."""
    def check(r):
        if r.accepted:
            return False, "accepted: " + ", ".join(_desc(c) for c in r.commands)
        reason = str(r.reject_reason)
        if reason.startswith(FORMAT_FAILURES):
            return False, f"format failure ({reason})"
        if not re.search(r"english|language", reason, re.I):
            return False, f"rejected as {reason}, not non-English"
        return True, ""
    return check


# (id, category, setup, utterance, checker) — task3_eval / hard_cases format
NOISE_CASES = [
    # --- English with noise: must be executed as meant ---
    ("N-E1", "noise", [], "wlak forwrad for four seconds", seq(go("fwd", dur=4))),
    ("N-E2", "noise", [], "turn left thirty degrease", seq(tn(30))),
    ("N-E3", "noise", [], "turn around walk forward one second",
     seq(tn(180, sign_free=True), go("fwd", dur=1))),
    ("N-E4", "noise", [], "turnright andthen stop", seq(tn(-90), stp())),
    ("N-E5", "noise", [], "okay so first turn left then walk forward three seconds then stop thanks",
     seq(tn(90), go("fwd", dur=3), stp())),
    ("N-E6", "noise", [], "walk to the blew chair", seq(gt("chair", "blue"))),
    ("N-E7", "noise", [], "reverse for won second", seq(go("back", dur=1))),
    ("N-E8", "noise", [], "pls turn rt 90 deg", seq(tn(-90))),
    ("N-E9", "noise", [], "sotp moving!", seq(stp())),
    ("N-E10", "noise", [], "um walk uh forward for like two seconds", seq(go("fwd", dur=2))),
    ("N-E11", "noise", [], "strafe lefft for three secods", seq(go("left", dur=3))),
    ("N-E12", "noise", [], "TURN ARROUND!!", seq(tn(180, sign_free=True))),
    ("N-E13", "noise", [], "go to the yellow stop sigh", seq(gt("stop sign", "yellow"))),
    ("N-E14", "noise", [], "walk forward for ate seconds", seq(go("fwd", dur=8))),

    # --- whole instruction in another language (Latin script): reject ---
    ("N-F1", "foreign", [], "recule pendant deux secondes", non_english()),          # fr: back up 2 s
    ("N-F2", "foreign", [], "camina hacia adelante tres segundos", non_english()),   # es: walk forward 3 s
    ("N-F3", "foreign", [], "dreh dich nach links", non_english()),                  # de: turn left
    ("N-F4", "foreign", [], "pusing ke kanan sembilan puluh darjah", non_english()), # ms: turn right 90 deg
    ("N-F5", "foreign", [], "jalan maju dua detik", non_english()),                  # id: walk forward 2 s

    # --- code-switching with a non-English content word: reject ---
    ("N-S1", "codeswitch", [], "go backwards 两秒", non_english()),                   # zh: two seconds
    ("N-S2", "codeswitch", [], "va tout droit for two seconds", non_english()),      # fr: go straight
    ("N-S3", "codeswitch", [], "go to the silla verde", non_english()),              # es: green chair
    ("N-S4", "codeswitch", [], "please jalan ke depan for two seconds", non_english()),  # ms: walk forward
    ("N-S5", "codeswitch", [], "walk vorwärts for two seconds", non_english()),      # de: forwards
]

STATES = {}   # no robot-state facts in this set

CATEGORIES = ["noise", "foreign", "codeswitch"]
