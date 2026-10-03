# Task 3.iv — LLM command parser evaluation

> **Upgrade (prompt v5, programs, talk-back, state, repair, Hard set):** see
> [`upgrade_eval.md`](upgrade_eval.md). v4 is now frozen in `eval/prompt_v4.py`; `--prompt v5` is the live prompt.

v1 and v2 were run on 2026-10-01 and v3 on 2026-10-02, all from branch `task_3_llm`; v4 (bonus, visual QA) on branch `bonus_b`. The system prompts compared are:

- **v1:** the original prompt, frozen in `eval/prompt_v1.py` (identical to `llm_parser.SYSTEM_PROMPT` at commit `3c2abc9`).
- **v2:** frozen in `eval/prompt_v2.py` (identical to `llm_parser.SYSTEM_PROMPT` at commit `8d07c45`). It adds a sign-convention block (vx + forward, **vy + LEFT**, wz + CCW, angle + left) and three few-shot examples: "turn right 90 degrees" → −90, "move left for two seconds" → vy +0.8, and "strafe right a bit" → vy −0.8.
- **v3:** frozen in `eval/prompt_v3.py`. It is v2 plus one rule line: "stop", "halt", "freeze", "stop now" and
  similar all map to `{"actions": [{"action": "stop"}]}` and are never rejected as empty. Alongside it, the parser
  now accepts a single bare action object (e.g. `{"action": "stop"}`) as a one-element list.
- **v4 (bonus):** the current `llm_parser.SYSTEM_PROMPT`: v3 plus a `look` action for questions about what the
  robot sees, two look few-shot examples, and two rules added after the v4 draft (see "Prompt v4" below).

There is no keyword-based post-fix in code; the direction must come from the LLM.

Raw per-call logs are in `eval/results/<prompt>/<service>.jsonl`, and the generated tables are in `eval/results/summary.md`.

## How to reproduce

ROS's `PYTHONPATH` breaks the project venv, so unset it for every command:

```bash
env -u PYTHONPATH .venv/bin/python -m pip install -r requirements.txt
env -u PYTHONPATH .venv/bin/python -m pytest -q tests/test_student_b.py      # offline, 42 tests
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --ping                 # one call per service
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --services qwen-flash gpt-5-nano --prompt v1 v2 --runs 3
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --services gemini-3.8-flash --prompt v1 v2 --runs 3 --budget 2
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --services qwen-flash gpt-5-nano --prompt v3 --runs 3
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --services gemini-3.8-flash --prompt v3 --runs 1 --budget 2
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --report               # rebuild summary.md
env -u PYTHONPATH .venv/bin/python eval/mock_main.py                         # full main.py loop on mocks
```

Use `--cases L1 L2 L3` to run only selected cases. The report merges them with earlier runs, keeping
the latest result per (run, case). API keys are read from the environment or from the git-ignored
repo-root `.env`: `DASHSCOPE_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`.

## Services, settings and pricing

All three services are called through the `openai` Python SDK (v3.22.1), using `chat.completions` with
`response_format={"type": "json_object"}`. The timeout is 15 s. Inside `_call_llm`, a network error or
5xx gets one retry. The eval adds pacing and exponential back-off on 429/5xx/network errors
(5, 10, 20, 40, 80 s). A call that still fails after that counts as an **API error**, never as a
parse error.

| Service key | Endpoint | Model id sent → returned | Extra params | Price, USD per 1M tokens in / out |
|---|---|---|---|---|
| `qwen-flash` | Alibaba Model Studio, Singapore (`dashscope-intl.aliyuncs.com/compatible-mode/v1`) | `qwen-flash` → `qwen-flash` (= `qwen-flash-2025-07-28`) | `temperature=0` | 0.05 / 0.40 (0–256K tier) |
| `gpt-5-nano` | OpenAI (`api.openai.com`) | `gpt-5-nano` → `gpt-5-nano-2025-08-07` | `reasoning_effort="minimal"` | 0.05 / 0.40 (standard) |
| `gemini-3.8-flash` | Google AI Studio, OpenAI-compatible (`generativelanguage.googleapis.com/v1beta/openai/`) | `gemini-3.8-flash` | `reasoning_effort="none"` (thinking off), default temperature; paced to ≤ 5 RPM | 0.75 / 3.75 (paid tier, until 2026-12-31) |

Pricing was checked on **2026-10-01**:
- [Alibaba Model Studio pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing)
- [OpenAI pricing](https://developers.openai.com/api/docs/pricing)
- [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)

Costs below are estimated from the token counts the APIs report.

**Gemini needed the paid tier.** Its free tier allows only 20 requests per day for
`gemini-3.8-flash` (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). One run needs 31 calls, so
an earlier attempt could not finish even one run. Billing was enabled for this round. A ping
confirmed the paid tier (HTTP 200, no free-tier quota error), and all 6 Gemini runs completed with
0 API errors: one connection error was retried successfully. **Gemini spend this round was
US$0.18 (186 calls)**, against a US$2 budget guard.

## Test set (31 utterances for v1/v2, 33 for v3; 3 runs per service and prompt)

| Category | n | Cases |
|---|---|---|
| basic | 5 | walk forward 3 s; turn left; turn right 45°; stop; go to the green chair |
| multi-step | 4 | walk 3 s then turn back; turn left, walk 2 s, then stop; back up 2 s then turn right; turn around and walk to the red ball |
| paraphrase | 8 | go straight ahead 3 s; "could you walk forwards a bit"; do a U-turn; head over to the green seat; move ahead slowly 4 s; rotate counter-clockwise by a quarter turn; halt!; shuffle sideways to your left 2 s (P8) |
| lateral (new) | 3 | **L1** sidestep to your left for two seconds; **L2** shuffle right for one second; **L3** slide over to the right a little. None copies a v2 few-shot example. |
| follow-up | 2 | "walk forward for two seconds" → "do that again, but slower"; "turn left 90 degrees" → "now the other way". The first turn goes into the history exactly as `chat_interface` builds it; only the second turn is scored. **F3** (v3 only): "go to the chair" → "the green one", expecting `goto_object(chair, green)`. |
| chat | 1 (+1) | what can you do?; **C2** (v3 only): "go to the chair", expecting a clarifying chat, because no colour was given. |
| invalid | 8 | fly to the roof; French; Chinese; whitespace; run forward for ten minutes; charge at a person; pick up a bottle; keyboard mash |

A case passes only if the whole `ParseResult` is right: the correct number and order of actions, the
correct types, and parameters within tolerance. Tolerances: angle ±1°, duration ±0.05 s; "normal" vx
in [0.5, 1]; "slow" vx in [0.1, 0.5]. Lateral moves need |vx| ≤ 0.1 and vy of the correct sign with
0.1 ≤ |vy| ≤ 1. Invalid inputs must be rejected (the keyboard mash may also get one clarifying
`chat`). The reject reason text is logged but not graded.

Latency and tokens are counted per LLM call. The Chinese and whitespace inputs are rejected by the
local precheck without an LLM call, so they are left out of those columns.

The v1 rows for Qwen and OpenAI reuse the earlier run of the 28 original cases (same prompt, same
settings). L1–L3 were run on v1 today, so **v1 and v2 are scored on the same 31-utterance set**.
Gemini ran both prompts in full today.

## Results

### Prompt v1

| Service | Run 1 | Run 2 | Run 3 | **Average** | API errors | Latency median / p90 (s) | Tokens in / out per call | Cost per 1k calls |
|---|---|---|---|---|---|---|---|---|
| qwen-flash | 87.1% | 87.1% | 87.1% | **87.1%** (81/93) | 0 | 0.35 / 0.54 | 980 / 30 | $0.061 |
| gpt-5-nano | 93.5% | 93.5% | 90.3% | **92.5%** (86/93) | 0 | 0.93 / 1.22 | 967 / 39 | $0.064 |
| gemini-3.8-flash | 100% | 100% | 100% | **100%** (93/93) | 0 | 1.81 / 2.41 | 1013 / 31 | $0.874 |

### Prompt v2

| Service | Run 1 | Run 2 | Run 3 | **Average** | API errors | Latency median / p90 (s) | Tokens in / out per call | Cost per 1k calls |
|---|---|---|---|---|---|---|---|---|
| qwen-flash | 100% | 100% | 100% | **100%** (93/93) | 0 | 0.35 / 0.52 | 1164 / 30 | $0.070 |
| gpt-5-nano | 100% | 96.8% | 96.8% | **97.8%** (91/93) | 0 | 1.02 / 1.23 | 1150 / 39 | $0.073 |
| gemini-3.8-flash | 100% | 100% | 100% | **100%** (93/93) | 0 | 2.03 / 2.34 | 1201 / 31 | $1.017 |

v2 adds about 185 prompt tokens per call (+15% cost) and doesn't change latency noticeably.

### Prompt v3

Gemini was run once on v3, as a regression check only. The full console output of the v3 runs is in
`eval/results/v3/eval.log`.

| Service | Run 1 | Run 2 | Run 3 | **Average** | API errors | Latency median / p90 (s) | Tokens in / out per call | Cost per 1k calls |
|---|---|---|---|---|---|---|---|---|
| qwen-flash | 100% | 100% | 100% | **100%** (99/99) | 0 | 0.35 / 0.55 | 1203 / 30 | $0.072 |
| gpt-5-nano | 100% | 100% | 100% | **100%** (99/99) | 0 | 1.09 / 1.38 | 1189 / 39 | $0.075 |
| gemini-3.8-flash | 100% | – | – | **100%** (33/33) | 0 | 1.96 / 2.27 | 1240 / 31 | $1.045 |

v3 adds about 38 prompt tokens per call over v2 (+3% cost). v3 is scored on 33 cases: the 31 above,
plus C2 and F3, which were added after the goto-without-colour fix. Those two were run on their own
with `--cases C2 F3` and merged into the same runs.

#### Goto without a colour (C2, F3; v3 prompt, code-side fix)

`navigation.goto_object` only matches an exact colour, so "go to the chair" used to parse to
`color=""` and end in a 360° search that couldn't succeed. Now `_to_command` turns a `goto_object` with
an empty colour into a chat: "Which chair do you mean? Please tell me its colour." The prompt is
unchanged.

| Service | C2 "go to the chair" → chat | F3 "the green one" (after C2) → goto(chair, green) |
|---|---|---|
| qwen-flash | 3/3 | 3/3 |
| gpt-5-nano | 3/3 | 3/3 |
| gemini-3.8-flash | 1/1 | 1/1 |

In every C2 call, all three models returned `goto_object(chair, color="")`. The question comes from
the parser, not the model. In F3, the model sees that question in the history and fills in the colour.

### Accuracy per category

| Service | Prompt | basic | multi-step | paraphrase | lateral | follow-up | chat | invalid |
|---|---|---|---|---|---|---|---|---|
| qwen-flash | v1 | 100% | 100% | 87.5% | **0%** | 100% | 100% | 100% |
| qwen-flash | v2 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| gpt-5-nano | v1 | 100% | 100% | 87.5% | **55.6%** | 100% | 100% | 100% |
| gpt-5-nano | v2 | 100% | 100% | 91.7% | 100% | 100% | 100% | 100% |
| gemini-3.8-flash | v1 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| gemini-3.8-flash | v2 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| qwen-flash | v3 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| gpt-5-nano | v3 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| gemini-3.8-flash | v3 (1 run) | 100% | 100% | 100% | 100% | 100% | 100% | 100% |

### Items that flipped between v1 and v2 (passes out of 3 runs)

| Service | Case | Utterance | v1 | v2 |
|---|---|---|---|---|
| qwen-flash | P8 | shuffle sideways to your left for two seconds | 0/3 | 3/3 |
| qwen-flash | L1 | sidestep to your left for two seconds | 0/3 | 3/3 |
| qwen-flash | L2 | shuffle right for one second | 0/3 | 3/3 |
| qwen-flash | L3 | slide over to the right a little | 0/3 | 3/3 |
| gpt-5-nano | P8 | shuffle sideways to your left for two seconds | 0/3 | 3/3 |
| gpt-5-nano | L1 | sidestep to your left for two seconds | 2/3 | 3/3 |
| gpt-5-nano | L2 | shuffle right for one second | 1/3 | 3/3 |
| gpt-5-nano | L3 | slide over to the right a little | 2/3 | 3/3 |
| gpt-5-nano | P7 | halt! | 3/3 | **1/3** (regression) |

Gemini didn't flip on anything: 31/31 in every run under both prompts.

### Items that flipped between v2 and v3

| Service | Case | Utterance | v2 | v3 |
|---|---|---|---|---|
| gpt-5-nano | P7 | halt! | 1/3 | **3/3** |

Only the "halt!" regression flipped: gpt-5-nano now returns a stop on every run. Nothing regressed.
qwen-flash stays at 93/93 and Gemini at 31/31. Every v3 P7 result was a wrapped stop. The log keeps
the raw text only for failures, so it doesn't show whether any of them needed the new bare-object path.
Caveat: the v3 rule names "halt" outright, so P7 is no longer a held-out case. v3's 100% on P7
confirms the fix, but it isn't evidence of generalisation.

## Prompt v4 / look (bonus: visual QA)

v4 adds `{"action": "look", "question": string}` for questions about what the robot can see right now. The
executor grabs one front-camera frame, runs the existing YOLO perception on it (`[DETECT]` lines), and sends the
same frame plus the question to a vision-language model (`dialogue/vlm.py`). It prints
`[VLM] model=… t=… tokens=in/out frame=…` and then `Robot: <answer>`. The VLM is told to answer only from the
image, in one or two sentences, and to say when it can't tell. Few-shot examples (deliberately not the eval
phrasings): "what's in front of you?" → look; "turn right and tell me if you see anything red" →
turn(−90), look.

New cases (category `look`): **V1** what can you see?, **V2** is there a chair in front of you?, **V3** what
colour is the ball ahead?, **V4** describe your surroundings → a look action; **V5** "look out!" → anything
*except* a look action. The v4 set is 38 cases (the 33 v3 cases + V1–V5), 1 run per service.

**v4 draft → v4.** The first v4 draft (prompt text and logs in `eval/results/v4_draft/`) scored qwen-flash
38/38, Gemini 38/38 and gpt-5-nano 36/38. gpt-5-nano's two failures were **V5** "look out!" → look (5/5 in
offline retries; v3 gave chat) and a real regression, **X2** "avancez tout droit" **accepted** as a forward
move (2 of 5 retries; 0 of 5 with v3). Two general rules fixed most of this:
- "Decide the language first: an instruction that is not in English is rejected as "non-English" even if you
  understand it." → X2 rejected 5/5 again.
- In the look description: only an actual question about what is visible is a look; "an exclamation or warning
  that happens to contain 'look' (like 'careful!') is not a look action; treat a warning as stop." → gpt-5-nano
  V5 3/5 non-look in retries; qwen-flash maps "look out!" to stop. The rule's example is "careful!", but the
  rule was written *because* of V5, so **V5 is no longer a held-out case**: its result below is a training-set
  number. gpt-5-nano's remaining V5 failure (37/38) is accepted, and the prompt is not tuned further.

| Service | v4 (38 cases) | the 33 v3 cases | look (V1–V5) | Latency median / p90 (s) | Tokens in / out | Cost per 1k calls |
|---|---|---|---|---|---|---|
| qwen-flash | **100%** (38/38) | 33/33 | 5/5 | 0.29 / 0.49 | 1415 / 28 | $0.082 |
| gpt-5-nano | **97.4%** (37/38) | 33/33 | 4/5 (V5 → look) | 1.12 / 1.45 | 1397 / 38 | $0.085 |
| gemini-3.8-flash | **100%** (38/38) | 33/33 | 5/5 | 2.15 / 2.74 | 1462 / 29 | $1.204 |

**Held-out warnings (V6–V8).** Since V5 is no longer held out, three new warning utterances were added after v4
was frozen. None of them is in the prompt. Each was run once per service, with no prompt changes afterwards
(2026-10-03, logged in `eval/results/v4/<service>.jsonl`). Pass means anything except a look action.

| Case | Utterance | qwen-flash | gpt-5-nano | gemini-3.8-flash |
|---|---|---|---|---|
| V6 | watch out! | ✅ stop | ✅ stop | ✅ stop |
| V7 | heads up, there's a wall | ✅ chat | ❌ `look("is there a wall ahead?")` | ✅ stop |
| V8 | careful, stop there | ✅ stop | ✅ stop | ✅ stop |
| | **held-out total** | 3/3 | 2/3 | 3/3 |

So gpt-5-nano generalises the warning rule only partly: an informative warning ("there's a wall") still reads to
it as a cue to look. qwen-flash passes V7, but with a chat reply rather than a stop. That's allowed under the
grading rule, but it isn't the "treat a warning as stop" behaviour the prompt asks for. With n = 1 per case, these
are spot checks, not rates. They don't change the recommendation (qwen-flash). Because `summary.md` merges V6–V8
into the v4 rows, its v4 totals there are out of 41 cases, not 38.

**No regressions against v3:** every one of the 33 v3 cases passes on v4 for all three services (the v3 → v4 flip
table in `eval/results/summary.md` is empty). The longer prompt adds about 210 input tokens per call (+17%).

### VLM choice: `config.VLM_SERVICE = "qwen3-vl-flash"`

Four candidates, the same system prompt, the same two sim frames
(`eval/results/vlm/probe_frame_turned_around.png`, `probe_frame_spawn.png`), 4 questions each (raw answers in
`eval/results/vlm/probe_candidates.jsonl`). Ground truth for the turned-around frame: a red stop sign close and
centred, green and yellow stop signs further away, a small orange ball half-hidden behind the pole, and the
edges of the red chair (left) and green chair (right). The spawn frame shows a blue chair on the stairs.

| Model | "what can you see?" | "is there a chair in front of you?" | "is there a ball anywhere?" | blue chair | Latency | Tokens in |
|---|---|---|---|---|---|---|
| **qwen3-vl-flash** | ✅ everything, incl. the chair edges | ✅ "red chair-like object to the left" | ✅ orange, behind the pole | ✅ | **0.4–1.4 s** | ~395 |
| gemini-3.8-flash | ✅ but calls the signs "markers" | ❌ "no chair" | ✅ | ✅ | 2.5–3.3 s | ~1150 |
| gpt-5-nano | ok | ❌ "no chair" | hedges ("not clearly a ball") | ✅ | 1.3–2.3 s | ~540 |
| qwen-vl-plus | misses the ball | ❌ can't confirm | ❌ "yellow ball" | ✅ | 0.3–0.7 s | ~395 |

qwen3-vl-flash was the most accurate (the only one to spot the half-visible chair) and the fastest of the
accurate models. It uses the same Alibaba endpoint and key as the parser.

### Real-sim check (main.py --gui, real skills + YOLO + qwen3-vl-flash, one fresh launch)

Typed: `turn around`, `what can you see?`, `turn right 45 degrees`, `is there a chair in front of you?`,
`turn left 135 degrees`, `what colour is the ball ahead?`. Poses come from the dry-run wrapper; full terminal
output is in `eval/results/vlm/real_sim_check.log`. The robot didn't move during a look, and nothing fell or
collided.

| Pose (x, y, yaw) | Frame | Question | VLM answer (qwen3-vl-flash, t) | YOLO `[DETECT]` on the same frame | Correct? |
|---|---|---|---|---|---|
| −0.09, 0.01, −176° (facing the red stop sign) | `eval/results/vlm/20261002-232010-231387.png` | what can you see? | "I see a red chair on the left, a large red square sign on a gray pole in the center, a green rectangular sign on a pole to the left of center, and a yellow rectangular sign on a pole to the right of center. The floor is a blue and dark-blue checkered grid…" (0.96 s) | `chair color=blue conf=0.50` (the red chair; "blue" is a stale-code artefact, see below); no stop signs, no ball | VLM ✅ (misses the half-hidden ball and the green chair sliver); YOLO partly (wrong colour, misses 3 signs) |
| −0.08, 0.03, 144° (green-chair area) | `eval/results/vlm/20261002-232018-702459.png` | is there a chair in front of you? | "Yes, there is a green chair in front of you, positioned toward the center-right of the view." (0.60 s) | `sports ball color=orange conf=0.73` only | VLM ✅; YOLO ❌ (misses the green chair) |
| −0.09, −0.02, −82° (open floor, terrain blocks on the left) | `eval/results/vlm/20261002-232027-560433.png` | what colour is the ball ahead? | "There is no ball visible ahead in the image." (0.46 s) | none | ✅ both |

**Correction (2026-10-03):** this run used `bonus_b`'s pre-`9da795e` `perception_real.py`. With main's (and the
fix branch's) colour grounding, the same box is labelled red. YOLO's real misses on these frames are the green
chair in frame 2 (conf 0.14 < 0.2), the stop signs and the half-hidden ball. Details: `eval/vlm_eval.md`.

On identical frames the VLM was right 3/3, while YOLO (current code) still missed an object in 2 of 3. That's the
expected trade-off: YOLO is local and gives boxes for navigation; the VLM gives a reliable
open-vocabulary answer but needs a network call (~0.5–1 s) and no geometry.

## Failure analysis

1. **Lateral sign inversion (v1), fixed by v2.**
   - **qwen-flash** inverted every lateral command, 12 out of 12: "left" became vy < 0 and "right"
     became vy > 0. It followed a screen-x convention and ignored v1's one-line `vy left(+)/right(-)`.
   - **gpt-5-nano** was inconsistent. Besides sign errors, it also turned "shuffle right" into a
     *forward* walk (vx 0.8, vy 0) or a forward arc (vx 0.8, wz −1). It also added forward motion to
     "slide over to the right" (vx 0.8, vy −0.3).
   - The validator can't catch either kind of error, because the values are well-formed and in range.
   - With v2's explicit sign table plus two lateral examples, every lateral case passes on all three
     services. This includes the three new phrasings that aren't in the examples ("sidestep",
     "shuffle", "slide over").
   - Gemini already got this right with v1.
2. **gpt-5-nano "halt!" regression (v2, 2 of 3 runs).**
   - In run 2 it returned `{"rejected": true, "reason": "empty"}`, treating the one-word exclamation as
     meaningless.
   - In run 3 it returned a bare `{"action": "stop"}` without the `{"actions": [...]}` wrapper. The
     strict validator rejects that as `invalid_field:actions`, as designed.
   - Both are fail-safe: the robot does nothing rather than doing something wrong. But a missed stop
     command matters.
   - Neither failure is in v1. The extra examples probably shifted gpt-5-nano's behaviour on very short
     inputs.
   - **Fixed in v3** with both remedies: a stop/halt/freeze rule line in the prompt, and accepting a
     single bare action object as a one-element list. Result: 3/3 on v3 (see the flip table above).
3. **Reject reasons aren't a closed vocabulary.** All invalid inputs were rejected by every service
   in every run (100%), but the reason text varies between models. For the keyboard mash, Qwen gave
   `non-English` and OpenAI gave `empty`; OpenAI also coined `out_of_range:ten_minutes`. Acceptance
   is unaffected.
4. **Latency and cost.** Gemini is the most accurate, but it is **~6× slower** (median 2.0 s vs 0.35 s)
   and **~15× more expensive** than qwen-flash. The free tier is unusable for this project: 20
   requests/day, plus frequent 503 "high demand" errors seen earlier the same day.

## Recommendation: `config.LLM_SERVICE = "qwen-flash"` (unchanged)

On v3, all three services score 100% (qwen-flash and gpt-5-nano 99/99, Gemini 33/33 in one run), so
accuracy no longer separates them. On the tie-break by latency, qwen-flash wins clearly: 0.35 s
median / 0.55 s p90, against gpt-5-nano's 1.09 s / 1.38 s and Gemini's 1.96 s / 2.27 s. It is also the
cheapest ($0.072 per 1k calls, vs $0.075 and $1.05).
`core/config.py` already has `LLM_SERVICE = "qwen-flash"`.

## Video_Task3 demo script

Recorded on the real sim on 2026-10-02 (`~/Videos/Video_Task3.mp4`, 54 s, not committed). Launch from
the repo root:

```bash
eval/run_env.sh main.py --gui      # browser panel at http://localhost:8765, camera "Third-person follow"
```

`eval/run_env.sh` unsets ROS's `PYTHONPATH`, points `QUADRUPED_MUJOCO_ROOT` at the sibling
`quadruped_mujoco` clone, and sets `MUJOCO_GL=egl` (see the EGL note below). Use a fresh launch for
every take, so the robot spawns at the origin. Type each line after the previous `[DONE]` or
`[CMD] rejected` line. The next `User:` prompt can appear before the `[EXEC]` lines; that's expected,
since input never blocks execution. On mocks (`eval/mock_main.py`) the same commands give the same
`[CMD]` lines.

**Why this order.** The robot spawns at the origin facing +x. The rough-terrain track starts at
x ≈ 1.5 m straight ahead, and the red stop sign is at (−1.3, 0) behind it. The original order
(`walk forward for three seconds` first) walked onto the track. In the dry run the 180° turn there ended
**136.7° off** and took 36.6 s. Turning left first sends every move along the clear strip at x ≈ 0
(±3.5 m in y), so the robot only ever walks on flat floor.

| # | What it shows | Type exactly | Lines in the recorded take | Pose after (x, y, yaw), dry run |
|---|---|---|---|---|
| a | single-step | `turn left 90 degrees` | `[CMD] actions=turn(90 deg) n=1`<br>`[EXEC] action=1/1 turn angle=90.0 deg`<br>`[TURN] target=90.0 deg final_error=1.8 deg`<br>`[DONE] actions=1 t=2.5 s` | 0.0, 0.0, 85° |
| b | multi-step: the handout's reference command | `walk forward for three seconds, then turn back` | `[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2`<br>`[EXEC] action=1/2 move vx=0.8 vy=0.0 wz=0.0 t=3.0 s`<br>`[EXEC] action=2/2 turn angle=180.0 deg`<br>`[TURN] target=180.0 deg final_error=1.6 deg`<br>`[DONE] actions=2 t=7.8 s` | 0.1, 2.3, −94° |
| c | second multi-step, with a right turn | `walk forward for two seconds, then turn right 90 degrees` | `[CMD] actions=move(vx=0.8, 2.0 s), turn(-90 deg) n=2`<br>`[EXEC] action=1/2 move vx=0.8 vy=0.0 wz=0.0 t=2.0 s`<br>`[EXEC] action=2/2 turn angle=-90.0 deg`<br>`[TURN] target=-90.0 deg final_error=-1.3 deg`<br>`[DONE] actions=2 t=4.0 s` | 0.0, 0.8, 178° |
| d | lateral move | `sidestep to your left for two seconds` | `[CMD] actions=move(vx=0, vy=0.8, 2.0 s) n=1`<br>`[EXEC] action=1/1 move vx=0.0 vy=0.8 wz=0.0 t=2.0 s`<br>`[DONE] actions=1 t=2.0 s` (robot moves to its **left**) | 0.0, −0.6, −178° |
| e | follow-up (uses history; type it right after d) | `do that again, but slower` | `[CMD] actions=move(vx=0, vy=0.3, 2.0 s) n=1`<br>`[EXEC] action=1/1 move vx=0.0 vy=0.3 wz=0.0 t=2.0 s`<br>`[DONE] actions=1 t=2.0 s` | 0.0, −1.1, −176° |
| f | rejected command | `fly to the roof` | `[CMD] rejected reason=impossible:fly` (no `[EXEC]`; robot stays put) | unchanged |
| g | non-English command | `avancez tout droit` | `[CMD] rejected reason=non-English` (rejected by the LLM, since the text is ASCII French) | unchanged |

The dry run (`eval/results/video_task3_dryrun.log`) logged contacts and tilt after every command. With
this order there was no contact with terrain or objects and no fall (max tilt 7.5°), and every turn
ended within 2°. The recorded take's terminal output is in `eval/results/video_task3_recording.log`.

**Optional: clarification (better in Video_Task4, since the robot then walks to the chair).** Type it
after g. On mocks, captured with qwen-flash and v3:

| # | Type exactly | Expected terminal lines |
|---|---|---|
| 8a | `go to the chair` | `[CMD] actions=chat n=1`<br>`Robot: Which chair do you mean? Please tell me its colour.`<br>`[DONE] actions=1 t=… s` |
| 8b | `the green one` | `[CMD] actions=goto_object(class=chair, color=green) n=1`<br>`[EXEC] action=1/1 goto_object class=chair color=green`<br>… navigation output … `[DONE] actions=1 t=… s` |

On mocks, 8b starts as shown, but navigation then keeps re-centring (`[DETECT]` / `[TURN] target=5.0 deg`),
because the mock bbox is fixed and off-centre. It doesn't reach `[DONE]` within a minute, so show 8b on the real sim only.

Optional extra: `向前走三秒` is rejected by the local precheck before any LLM call, with the same
`reason=non-English`.

Notes for recording:

- **(Video_Task3 only — superseded on b/upgrade by the stop fast path, `[ESTOP]`, see eval/upgrade_eval.md.)** **Don't demo a mid-move stop.** The executor runs each move to completion (`skills.move()` blocks),
  so a "stop" typed during a move is only queued. It runs after the move has already finished, so on
  camera it looks like stop did nothing. "stop" on its own is parsed correctly (P7 / M2 in the eval).
- **No `goto_object` in this video**, apart from the optional step 8. Object search and approach belong in Video_Task4.
- **Stop the screen recorder before pressing Ctrl+C** in the demo terminal. Ctrl+C prints a
  `KeyboardInterrupt` traceback plus EGL clean-up errors from the render thread.

## EGL note (for Student C / Task 4)

Under the default MuJoCo GL backend (GLFW/GLX), `RealSkills.get_camera_frame()` returns **all-black
frames** on this machine (Ubuntu, X11, NVIDIA). `mujoco.Renderer` is created on the main thread but
renders on the sim thread, and a GLX context can't be made current on another thread (`GLFWError 65544:
GLX: Failed to make context current`). Perception then sees nothing, which looks like a navigation
failure. With `MUJOCO_GL=egl`, the first render fails once with `EGL_BAD_ACCESS`, the self-heal in
`_maybe_render_camera` recreates the renderer on the sim thread, and frames are real from then on
(checked: mean pixel 88 vs 0). `eval/run_env.sh` sets `MUJOCO_GL=egl` by default, except with
`--native`, which needs GLFW for its window. The one `[CAMERA] render failed (EGLError …)` line at
startup is that recovery and is harmless. The browser panel's live view renders either way. Only the
dog's onboard camera is affected.

