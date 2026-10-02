# Task 3.iv — LLM command parser evaluation

v1 and v2 were run on 2026-10-01 and v3 on 2026-10-02, all from branch `task_3_llm`. The three system prompts compared are:

- **v1:** the original prompt, frozen in `eval/prompt_v1.py` (identical to `llm_parser.SYSTEM_PROMPT` at commit `3c2abc9`).
- **v2:** frozen in `eval/prompt_v2.py` (identical to `llm_parser.SYSTEM_PROMPT` at commit `8d07c45`). It adds a sign-convention block (vx + forward, **vy + LEFT**, wz + CCW, angle + left) and three few-shot examples: "turn right 90 degrees" → −90, "move left for two seconds" → vy +0.8, and "strafe right a bit" → vy −0.8.
- **v3:** the current `llm_parser.SYSTEM_PROMPT`. It is v2 plus one rule line: "stop", "halt", "freeze", "stop now" and
  similar all map to `{"actions": [{"action": "stop"}]}` and are never rejected as empty. Alongside it, the parser
  now accepts a single bare action object (e.g. `{"action": "stop"}`) as a one-element list.

There is no keyword-based post-fix in code; the direction must come from the LLM.

Raw per-call logs are in `eval/results/<prompt>/<service>.jsonl`, and the generated tables are in `eval/results/summary.md`.

## How to reproduce

ROS's `PYTHONPATH` breaks the project venv, so unset it for every command:

```bash
env -u PYTHONPATH .venv/bin/python -m pip install -r requirements.txt
env -u PYTHONPATH .venv/bin/python -m pytest -q tests/test_student_b.py      # offline, 38 tests
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

## Test set (31 utterances, 3 runs per service and prompt)

| Category | n | Cases |
|---|---|---|
| basic | 5 | walk forward 3 s; turn left; turn right 45°; stop; go to the green chair |
| multi-step | 4 | walk 3 s then turn back; turn left, walk 2 s, then stop; back up 2 s then turn right; turn around and walk to the red ball |
| paraphrase | 8 | go straight ahead 3 s; "could you walk forwards a bit"; do a U-turn; head over to the green seat; move ahead slowly 4 s; rotate counter-clockwise by a quarter turn; halt!; shuffle sideways to your left 2 s (P8) |
| lateral (new) | 3 | **L1** sidestep to your left for two seconds; **L2** shuffle right for one second; **L3** slide over to the right a little. None copies a v2 few-shot example. |
| follow-up | 2 | "walk forward for two seconds" → "do that again, but slower"; "turn left 90 degrees" → "now the other way". The first turn goes into the history exactly as `chat_interface` builds it; only the second turn is scored. |
| chat | 1 | what can you do? |
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
| qwen-flash | 100% | 100% | 100% | **100%** (93/93) | 0 | 0.37 / 0.55 | 1202 / 30 | $0.072 |
| gpt-5-nano | 100% | 100% | 100% | **100%** (93/93) | 0 | 1.08 / 1.38 | 1188 / 40 | $0.075 |
| gemini-3.8-flash | 100% | – | – | **100%** (31/31) | 0 | 1.96 / 2.27 | 1240 / 31 | $1.046 |

v3 adds about 38 prompt tokens per call over v2 (+3% cost).

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

On v3, all three services score 100% (qwen-flash and gpt-5-nano 93/93, Gemini 31/31 in one run), so
accuracy no longer separates them. On the tie-break by latency, qwen-flash wins clearly: 0.37 s
median / 0.55 s p90, against gpt-5-nano's 1.08 s / 1.38 s and Gemini's 1.96 s / 2.27 s. It is also the
cheapest ($0.072 per 1k calls, vs $0.075 and $1.05).
`core/config.py` already has `LLM_SERVICE = "qwen-flash"`.

## Video_Task3 demo script

Run the real sim with `main.py` (A/C's flags are already True), or rehearse on mocks with
`env -u PYTHONPATH .venv/bin/python eval/mock_main.py`. Keep the terminal visible throughout. Type
each line after the previous `[DONE]` or `[CMD] rejected` line.

The expected lines below were captured on mocks with qwen-flash and prompt v2. With the real
`RealSkills`, `[DONE] t=` shows the real execution time and the `[MOCK …]` lines are replaced by the
sim's own output. Because the chat thread runs in parallel, the next `User:` prompt can appear before
the `[EXEC]` lines. That's expected: input never blocks execution.

| # | What it shows | Type exactly | Expected terminal lines |
|---|---|---|---|
| 1 | single-step | `walk forward for three seconds` | `[CMD] actions=move(vx=0.8, 3.0 s) n=1`<br>`[EXEC] action=1/1 move vx=0.8 vy=0.0 wz=0.0 t=3.0 s`<br>`[DONE] actions=1 t=… s` |
| 2 | multi-step with a turn | `walk forward for two seconds, then turn right 90 degrees` | `[CMD] actions=move(vx=0.8, 2.0 s), turn(-90 deg) n=2`<br>`[EXEC] action=1/2 move vx=0.8 vy=0.0 wz=0.0 t=2.0 s`<br>`[EXEC] action=2/2 turn angle=-90.0 deg`<br>`[DONE] actions=2 t=… s` |
| 3 | lateral move | `sidestep to your left for two seconds` | `[CMD] actions=move(vx=0, vy=0.8, 2.0 s) n=1`<br>`[EXEC] action=1/1 move vx=0.0 vy=0.8 wz=0.0 t=2.0 s`<br>`[DONE] actions=1 t=… s` (robot moves to its **left**) |
| 4 | follow-up (uses history) | `do that again, but slower` | `[CMD] actions=move(vx=0, vy=0.3, 2.0 s) n=1` (same direction, lower speed)<br>`[EXEC] action=1/1 move vx=0.0 vy=0.3 wz=0.0 t=2.0 s`<br>`[DONE] actions=1 t=… s` |
| 5 | rejected command | `fly to the roof` | `[CMD] rejected reason=impossible:fly` (no `[EXEC]`; robot stays put) |
| 6 | non-English command | `avancez tout droit` | `[CMD] rejected reason=non-English` (rejected by the LLM, since the text is ASCII French) |

Optional extra: `向前走三秒` is rejected by the local precheck before any LLM call, with the same
`reason=non-English`.
