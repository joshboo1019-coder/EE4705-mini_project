# Task 3.iv — LLM command parser evaluation

Run on 2026-10-01 from branch `task_3_llm`. Raw per-call logs are in
`eval/results/<service>.jsonl`, and the generated tables are in `eval/results/summary.md`.

## How to reproduce

ROS's `PYTHONPATH` breaks the project venv, so unset it for every command:

```bash
env -u PYTHONPATH .venv/bin/python -m pip install -r requirements.txt   # adds python-dotenv, pytest
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --ping             # one call per service
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --services qwen-flash gpt-5-nano --runs 3
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --services gemini-3.8-flash --runs 3   # paced, see below
env -u PYTHONPATH .venv/bin/python eval/task3_eval.py --report           # rebuild summary.md
env -u PYTHONPATH .venv/bin/python -m pytest -q tests/test_student_b.py  # offline parser tests (26 pass)
env -u PYTHONPATH .venv/bin/python eval/mock_main.py                     # full main.py loop on mocks
```

API keys are read from the environment, or else from the repo-root `.env` (git-ignored):
`DASHSCOPE_API_KEY`, `GOOGLE_API_KEY`, `OPENAI_API_KEY`.

## Services and exact settings

All three services are called through the `openai` Python SDK (v3.22.1), using `chat.completions` with
`response_format={"type": "json_object"}`. Every call uses the same system prompt
(`llm_parser.SYSTEM_PROMPT`: schema, conventions, and 7 few-shot examples). The timeout is 15 s. On a
network error or 5xx, the parser retries once.

| Service key | Provider / endpoint | Model id sent | Model id returned | Extra params | Price (USD / 1M tok, in / out) |
|---|---|---|---|---|---|
| `qwen-flash` | Alibaba Model Studio, Singapore (`dashscope-intl.aliyuncs.com/compatible-mode/v1`) | `qwen-flash` | `qwen-flash` (alias for `qwen-flash-2025-07-28`, per the pricing page) | `temperature=0` | 0.05 / 0.40 (0–256K tier) |
| `gpt-5-nano` | OpenAI (`api.openai.com`) | `gpt-5-nano` | `gpt-5-nano-2025-08-07` | `reasoning_effort="minimal"` (no temperature on gpt-5) | 0.05 / 0.40 |
| `gemini-3.8-flash` | Google AI Studio, OpenAI-compatible (`generativelanguage.googleapis.com/v1beta/openai/`) | `gemini-3.8-flash` | — | `reasoning_effort="none"` (thinking off), default temperature | 0.75 / 3.75 (paid tier, until 2026-12-31; the free tier used here costs $0) |

Prices were checked on 2026-10-01 at alibabacloud.com/help/en/model-studio/model-pricing,
developers.openai.com/api/docs/pricing, and ai.google.dev/gemini-api/docs/pricing.

## Test set (26 utterances, 3 runs per service)

| Category | n | Cases |
|---|---|---|
| basic | 5 | walk forward 3 s; turn left; turn right 45°; stop; go to the green chair |
| multi-step | 4 | walk 3 s then turn back; turn left, walk 2 s, then stop; back up 2 s then turn right; turn around and walk to the red ball |
| paraphrase | 8 | go straight ahead 3 s; "could you walk forwards a bit"; do a U-turn; head over to the green **seat**; move ahead slowly 4 s; rotate counter-clockwise by a quarter turn; halt!; shuffle sideways to your left 2 s |
| follow-up | 2 | "walk forward for two seconds" → "do that again, but slower"; "turn left 90 degrees" → "now the other way" (history built exactly as `chat_interface` does; only the 2nd turn is scored) |
| chat | 1 | what can you do? |
| invalid / out of scope | 8 | fly to the roof; French; Chinese; whitespace only; run forward for ten minutes (> 30 s); charge at a person; pick up a bottle; keyboard mash |

A case passes only if the whole `ParseResult` is right: the correct number and order of actions, the
correct action types, and parameters within tolerance. Tolerances: angle ±1°, duration ±0.05 s,
"normal" vx in [0.5, 1], "slowly" vx in [0.1, 0.5]. Invalid cases must be rejected (the keyboard mash
may also get a single clarifying `chat`). The reject reason text is logged but not graded.

Latency and tokens are measured per LLM call. The Chinese and whitespace-only inputs are rejected by
the local precheck without calling the LLM, so they are left out of those columns.

## Results

| Service | Complete runs | Accuracy | basic | multi-step | paraphrase | follow-up | chat | invalid | Latency mean / median / p95 (s) | Tokens in / out per call | Cost per call (USD) | Cost per 1k calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen-flash | 3 | 96% (81/84) | 100% | 100% | 88% | 100% | 100% | 100% | 0.36 / 0.29 / 0.57 | 981 / 29 | 0.000061 | $0.061 |
| gpt-5-nano | 3 | 96% (81/84) | 100% | 100% | 88% | 100% | 100% | 100% | 0.97 / 0.93 / 1.41 | 968 / 38 | 0.000064 | $0.064 |
| gemini-3.8-flash | **0** (free-tier daily quota, see below) | — | | | | | | | | | | |

Both services gave identical answers in all 3 runs, so their outputs were fully stable at these
settings. No service errors occurred for Qwen or OpenAI.

### Gemini: no complete run possible on the free tier

The call pacing was ≤ 5 RPM (13 s between calls), with backoff on 429 and 503. The first run stopped
after 2 calls with the following error:

```
429 RESOURCE_EXHAUSTED  quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier
metric: generate_content_free_tier_requests, quotaValue: 20, model: gemini-3.8-flash
```

The free tier allows **20 requests per day** for this model. One full run needs 28 LLM calls (26
cases, minus the 2 caught by the precheck, plus 2 follow-up setup turns), so **no complete run fits in
a day's quota**. Most of today's 20 requests had already gone to `--ping` and to debugging calls. Many of those failed
with **503 "model is currently experiencing high demand"**, and these apparently count against the
quota too.

The partial run was discarded and is not counted as parse failures. The 1 Gemini call that finished
before the quota ran out (B1) parsed correctly. Getting Gemini numbers needs a billed project; at the
prices above, one 3-run eval would cost ≈ $0.25.

## Failure-case analysis

1. **Lateral direction sign inverted (P8, both services, every run).** "shuffle sideways to your
   left" produced `vy = -0.8`, which is a move to the *right* (the schema has left as +). The prompt
   says `vy left(+)/right(-)`, but none of the few-shot examples uses `vy`. Probing outside the eval
   set shows the error is systematic:

   | Input | qwen-flash vy | gpt-5-nano vy |
   |---|---|---|
   | move left 2 s | -0.8 ✗ | -0.8 ✗ |
   | strafe left 2 s | -0.8 ✗ | -0.8 ✗ |
   | step to the right 2 s | +0.8 ✗ | -0.3 ✓ |

   The models seem to follow a screen/x-axis convention (left = negative) and ignore the stated sign.
   The robot would walk the wrong way. The validator can't catch this because the value is
   well-formed and in range. Likely fix (not applied, to keep these results valid): add a `vy`
   few-shot example such as "move left for two seconds" → `vy: 0.8`, then re-run the eval.
2. **Reject reasons are inconsistent across models.** All 24 invalid inputs were rejected, but the
   reason text varies. For the keyboard mash, Qwen said `non-English` and OpenAI said `empty`.
   OpenAI also coined variants like `out_of_range:ten_minutes` and `impossible:picking_up_objects`.
   Acceptance is unaffected, but the reasons aren't a closed vocabulary. For the video that's fine; a
   UI that branched on reasons would need an enum.
3. **Gemini availability.** Even before the quota ran out, the free tier returned 503 on most of the calls
   made today. In a live demo that adds 1–15 s of retry delay per command, or ends in an
   `llm_error:InternalServerError` rejection.

## Conclusion

On this test set, qwen-flash and gpt-5-nano are equally accurate (96%, with the same single failure),
and both cost about $0.06 per 1,000 commands. qwen-flash is **~2.7× faster** (median 0.29 s vs
0.93 s), so it stays the default `config.LLM_SERVICE`.
