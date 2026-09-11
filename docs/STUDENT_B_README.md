# Student B — Task 3: LLM Command Parser & Chat Interface (60%)

You own the entire `dialogue/` folder: `llm_parser.py`, `executor.py`,
`chat_interface.py`. It's your own directory — nobody else edits inside it.

You do **not** need Student A's simulation or Student C's YOLO to be ready.
Your code only ever talks to `core.interfaces.SkillsAPI` /
`core.interfaces.PerceptionAPI`, and you already have working stand-ins
for both (`skills/skills_mock.py`, `perception/perception_mock.py`). Build
and test your whole pipeline today. Run everything from the project root
(`minilab_1_3/`).

## 1. Setup on your laptop

You don't need MuJoCo installed to develop your part (though installing it
per the main README lets you eventually run the full system). You do need:

```bash
conda create -n quadruped_mujoco python=3.11 -y
conda activate quadruped_mujoco
pip install openai pyyaml
# plus whichever LLM SDKs you're comparing, e.g.:
pip install google-genai      # for Gemini
# Alibaba Cloud Model Studio (Qwen) exposes an OpenAI-compatible endpoint,
# so the `openai` package works for it too — just point base_url at it.
```

Get API keys / free-tier access for **at least two** services (pick from
the handout's Section V table — OpenAI, Alibaba Cloud Qwen, Google
Gemini, or local Ollama). Export them as environment variables, never
commit them:

```bash
export OPENAI_API_KEY=sk-...
export DASHSCOPE_API_KEY=...      # Alibaba Cloud (Qwen)
export GOOGLE_API_KEY=...         # Gemini
```

## 2. What you're building

1. **`dialogue/llm_parser.parse_command(user_text, history)`** — turns one
   utterance into a `core.schema.ParseResult` using the JSON command
   schema already defined in `core/schema.py` / documented in
   `llm_parser.SYSTEM_PROMPT`. Fill in `_call_llm()` — that's the one
   `NotImplementedError` standing between you and a working parser. Must:
   - handle multi-step instructions as an ordered list
   - handle paraphrases ("go straight ahead", "could you walk forwards a bit")
   - reject impossible / unsafe / empty / non-English input (print
     `[CMD] rejected reason=...`)
   - print `[CMD] actions=... n=...` on success (already wired up for you)
2. **`dialogue/chat_interface.py`** — the threaded terminal loop. Already
   implemented; maintains dialogue `history` so follow-ups like "do that
   again, but slower" can be resolved by the LLM. Runs in its own thread
   so it never blocks the simulation.
3. **`dialogue/executor.py`** — pops commands off the queue and calls
   `skills.move()` / `skills.turn()` / `navigation.goto_object()` in
   order, printing `[EXEC]` / `[DONE]`. Already implemented against the
   interfaces — you shouldn't need to touch this unless you're adding a
   new command type. (Why validation lives entirely in the parser and the
   executor stays a pure dispatcher: [`docs/DECISIONS.md`](DECISIONS.md) §5.)

Before and after any change here, `python -m pytest -q tests/test_architecture.py`
should stay green — it's the mechanical check that this folder never
imports `skills.skills_real` or `perception.perception_real` directly.

## 3. Test entirely on your own

```bash
python tests/test_student_b.py
```

This runs your parser + executor against `MockSkills` / `MockPerception`
end to end, with test utterances including a multi-step command, a
goto_object command, and two that should be rejected. Once `_call_llm()`
is implemented this should run cleanly without any of Student A's or
Student C's real code existing yet.

For the Task 3.iv evaluation, write a small driver script (or extend the
test above) that runs ≥20 utterances — ≥5 paraphrases, ≥5 invalid/OOS —
through **both** LLM services you chose, and log accuracy / latency / cost
per call into a table for the report.

## 4. Handing off to the group

Your code needs no changes at integration time — it was written entirely
against the interfaces. When Student A's and Student C's real modules are
ready, `main.py`'s flags flip and your parser/executor just start being
called with the real sim/detector instead of the mocks.

## 5. Deliverables checklist (Task 3)

- [ ] Structured-output prompting method summarized/justified in the report
- [ ] Parser handles multi-step instructions, paraphrases, and rejections
- [ ] `[CMD]` / `[CMD] rejected reason=...` lines printed correctly
- [ ] Chat loop runs in its own thread; simulation never blocks on it
- [ ] Dialogue history supports follow-up references
- [ ] ≥20-utterance evaluation table across ≥2 LLM services (accuracy,
      latency, cost) in the report, with failure-case analysis
- [ ] `Video_Task3`: terminal visible throughout, typed command visible,
      autonomous execution to `[DONE]`, one multi-step command with a
      turn, one rejected command
