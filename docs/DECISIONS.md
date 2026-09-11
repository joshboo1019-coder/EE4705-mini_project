# Backbone design decisions

Owner: backbone (ALL)

This records *why* the contracts in `core/` are shaped the way they are,
so a design choice doesn't get silently re-litigated (or silently broken)
partway through the project. If a choice below needs to change, it's a
`core/schema.py` / `core/interfaces.py` change — see the Contract
evolution rules in the root README before touching either file.

`CONTRACT_VERSION = 1` (in `core/schema.py`). Bump it whenever a change
below would be semantic (new required field, removed field, changed
meaning) rather than purely additive.

## 1. Two interfaces, not three

The handout's architecture (Fig. 1) has three moving pieces — platform,
perception, dialogue — but only two of them needed to become an
abstract contract: `SkillsAPI` (Task 2) and `PerceptionAPI` (Task 4).
Task 3's dialogue/parsing/execution loop is the *consumer* of both, not a
third interface for someone else to implement against — nothing else in
the system needs to swap out Student B's logic for a mock, because
Student B's logic *is* the orchestration, not a leaf module. This is why
`dialogue/` imports `core.interfaces` but nothing implements an interface
named after it.

## 2. Why `move()` and `turn()` are separate methods, not one `drive()`

The handout requires `turn()` to be **closed-loop** (true yaw feedback)
and explicitly asks for a report comparison against open-loop timing —
that's a distinct algorithm from a timed velocity command, not a
parameter of the same one. Keeping them as two methods on `SkillsAPI`
means Student A can implement, test, and show the open-loop-vs-closed-loop
comparison independently of the general `move()` path.

## 3. Why `goto_object` lives in `perception/navigation.py`, not `dialogue/`

`goto_object(class, color)` is one *command* (defined in `core/schema.py`
and produced by Student B's parser), but its *implementation* — search,
steer-to-center, approach, the C1–C3 "found" definition — is entirely
Task 4 territory and needs both `SkillsAPI` and `PerceptionAPI` to do its
job. Putting it in `perception/` keeps Student C's search-and-approach
logic testable in isolation (`tests/test_student_c.py`) without dragging
in the LLM parser, and keeps `dialogue/executor.py` a thin dispatcher that
never contains navigation logic of its own.

## 4. Why ground-truth object positions are a `config` dict, not part of `PerceptionAPI`

`config.OBJECT_POSITIONS` exists **only** to compute the distance logged
in `[FOUND] ... d=...`, per the handout's Definition of "found" (C1–C3).
It is deliberately not reachable through `PerceptionAPI` or `SkillsAPI` —
if it were, it would be one line of temptation away from being used to
steer the robot instead of the camera. Keeping it a plain config constant
that only `navigation.goto_object`'s logging step touches is what makes
"never used to steer" an structural property instead of a promise.

## 5. Why the command queue is thread-safe but commands aren't validated twice

`chat_interface.py` runs in its own thread so the simulation and the LLM
call never block each other; `core.schema.CommandQueue` wraps
`queue.Queue` for that handoff. Validation (rejecting malformed/unsafe
commands) happens once, inside `llm_parser._to_parse_result`, before
anything reaches the queue — the executor trusts anything it pops. This
keeps `executor.py` a pure dispatcher and keeps "why was this rejected"
traceable to one place (`[CMD] rejected reason=...`) instead of two.

## 6. Why `skills_mock.py` / `perception_mock.py` ship in the repo instead of living only in tests

Student B and Student C's own logic (`llm_parser.py`, `executor.py`,
`navigation.py`) needs a `SkillsAPI` / `PerceptionAPI` implementation to
run against from day one, before Student A's simulation or Student C's
detector exists. Making the mocks first-class modules (not test-only
fixtures) is what makes `python -m skills.skills_real`-style standalone
development possible for all three people at once — see
`docs/STUDENT_README.md` §1.
