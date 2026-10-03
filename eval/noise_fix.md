# Prompt v5.1: is misspelt English still English? (noise vs. code-switching)

**Result: v5.1 is a trade-off, not a fix, so I don't recommend merging it.** On the held-out set N it
fixes noisy English on qwen-flash, the deployed service: noise went from 31/42 to 38/42, and no
noisy English was rejected as non-English (8 such rejections before). But qwen-flash then also
executes non-English commands: must-reject went from 24/30 to 18/30, and 12 of 30 must-reject
replies were executed instead of 6. On gpt-5-nano the noise gain is small (31 to 33/42), and it
too loses rejections (29 to 25/30). The Standard set does not change. No out-of-bounds command
passed the validator in any run.

## Problem

Prompt v5 added this rule: "an instruction that mixes in words or numbers from another language is
non-English". On the Hard set (`eval/hard_cases.py`), qwen-flash's **noise** category fell from 8/8
with v4 to 4/8 with v5, and gpt-5-nano scored 4/8. The cheap models rejected typo-laden English such as
"trun lfet nintey degres" as non-English, with the right suggestion attached. The Hard set's noise and
code-switch categories have now been looked at, so they cannot be used to validate a fix.

## Method: what was held out, and when

| Step | Commit | What |
|---|---|---|
| 1 | `cecfb7a` | **Set N written and committed first**, on its own (`eval/noise_cases.py`, 24 cases), before any change to the language rule |
| 2 | `8cc50c3` | v5 frozen as `eval/prompt_v5.py`; `task3_eval.py --set noise`; **v5 baseline on N** |
| 3 | `944c05f` | **v5.1 written once and committed before any v5.1 run.** It is not tuned on N. |
| 4 | this commit | v5.1 runs: N (primary), Standard, Hard; this report |

**Set N.**
- **noise (14):** clearly English commands that must be executed. They contain typos, swapped
  letters, sound-alike words (e.g. "blew" for blue, "won" for one, "ate" for eight), dropped
  conjunctions, missing spaces, abbreviations, filler words, run-on text and all-caps.
- **foreign (5):** whole sentences in French, Spanish, German, Malay or Indonesian, all in Latin
  script. They must be rejected as non-English.
- **codeswitch (5):** an English command with one content word from Chinese, French, Spanish,
  Malay or German. It must be rejected as non-English.

The must-reject check is stricter than the Hard set's `rej()`: the reject reason must name the
language. A test checks that N shares no phrasing with the Hard set, the Standard set or the
few-shot examples of prompts v1–v5.1, and that no N phrasing appears inside any prompt. The local
precheck rejects none of the 24 cases, so the LLM decides every one.

**The v5.1 change.** One rule is added after v5's language rule. Nothing else changes, and a test
(`test_v5_1_is_v5_plus_one_language_rule`) checks that. No few-shot example was added:

> - Misspelt, misheard or garbled ENGLISH is still English, never "non-English". Typed and
>   speech-recognised commands often contain typos, swapped, missing or doubled letters, missing or
>   extra spaces, abbreviations, filler words, missing punctuation, and wrong English words that
>   sound like the intended ones. Read such an instruction as the English it was meant to be and
>   parse it normally (it is not rejected and needs no suggestion). Only a real word of another
>   language, or text in another script, makes an instruction non-English.

**Runs.** Each prompt ran on qwen-flash and gpt-5-nano. Set N got 3 runs per prompt: the specified
run plus 2 more, because N is small and both models vary between runs (qwen-flash too, despite
temperature 0). The Standard and Hard sets got 1 run of v5.1, compared with the logged v5 runs.
gemini-3.8-flash was skipped for cost; it already scored 8/8 noise and 8/8 codeswitch on the Hard
set with v5. The tables can be regenerated with `eval/noise_report.py`, which makes no API calls.

## Results

### Set N (held out for v5.1)

| Service | Prompt | noise (14) run 1 | runs 2, 3 | **noise, 3 runs** | foreign, 3 runs | codeswitch, 3 runs | must-reject (10) run 1 | runs 2, 3 | **must-reject, 3 runs** | all 24, 3 runs |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen-flash | v5 | 11/14 | 10/14, 10/14 | **31/42** | 12/15 | 12/15 | 8/10 | 8/10, 8/10 | **24/30** | 55/72 |
| qwen-flash | v5.1 | 13/14 | 12/14, 13/14 | **38/42** | 9/15 | 9/15 | 6/10 | 6/10, 6/10 | **18/30** | 56/72 |
| gpt-5-nano | v5 | 13/14 | 9/14, 9/14 | **31/42** | 15/15 | 14/15 | 9/10 | 10/10, 10/10 | **29/30** | 60/72 |
| gpt-5-nano | v5.1 | 13/14 | 11/14, 9/14 | **33/42** | 13/15 | 12/15 | 9/10 | 8/10, 8/10 | **25/30** | 58/72 |

How the failures break down (3 runs each):

| Service | Prompt | noise rejected as non-English | noise executed WRONGLY | must-reject EXECUTED | unsafe passed validator |
|---|---|---|---|---|---|
| qwen-flash | v5 | 8 | 0 | 6 | 0 |
| qwen-flash | v5.1 | **0** | 1 | **12** | 0 |
| gpt-5-nano | v5 | 7 | 2 | 1 | 0 |
| gpt-5-nano | v5.1 | 3 | **6** | **5** | 0 |

Per case (passes out of 3 runs):

| Case | Utterance | qwen v5 | qwen v5.1 | nano v5 | nano v5.1 |
|---|---|---|---|---|---|
| N-E1 | wlak forwrad for four seconds | 3/3 | 3/3 | 2/3 | 2/3 |
| N-E2 | turn left thirty degrease | 3/3 | 3/3 | 3/3 | 3/3 |
| N-E3 | turn around walk forward one second | 3/3 | 3/3 | 3/3 | 3/3 |
| N-E4 | turnright andthen stop | 3/3 | 3/3 | 3/3 | 3/3 |
| N-E5 | okay so first turn left then walk forward three seconds then stop thanks | 3/3 | 3/3 | 3/3 | 2/3 |
| N-E6 | walk to the blew chair | 0/3 | **3/3** | 1/3 | 2/3 |
| N-E7 | reverse for won second | 1/3 | **3/3** | 2/3 | 2/3 |
| N-E8 | pls turn rt 90 deg | 3/3 | 3/3 | 3/3 | 3/3 |
| N-E9 | sotp moving! | 3/3 | 3/3 | 3/3 | 3/3 |
| N-E10 | um walk uh forward for like two seconds | 3/3 | 3/3 | 1/3 | 3/3 |
| N-E11 | strafe lefft for three secods | 0/3 | 2/3 | 1/3 | 1/3 |
| N-E12 | TURN ARROUND!! | 3/3 | 3/3 | 3/3 | 3/3 |
| N-E13 | go to the yellow stop sigh | 3/3 | 3/3 | 3/3 | 3/3 |
| N-E14 | walk forward for ate seconds | 0/3 | 0/3 | 0/3 | 0/3 |
| N-F1 | recule pendant deux secondes | 3/3 | 3/3 | 3/3 | 3/3 |
| N-F2 | camina hacia adelante tres segundos | 0/3 | 0/3 | 3/3 | 3/3 |
| N-F3 | dreh dich nach links | 3/3 | 3/3 | 3/3 | 3/3 |
| N-F4 | pusing ke kanan sembilan puluh darjah | 3/3 | 3/3 | 3/3 | 3/3 |
| N-F5 | jalan maju dua detik | 3/3 | **0/3** | 3/3 | **1/3** |
| N-S1 | go backwards 两秒 | 3/3 | 3/3 | 3/3 | 3/3 |
| N-S2 | va tout droit for two seconds | 3/3 | **0/3** | 3/3 | 3/3 |
| N-S3 | go to the silla verde | 0/3 | 0/3 | 2/3 | 2/3 |
| N-S4 | please jalan ke depan for two seconds | 3/3 | 3/3 | 3/3 | 3/3 |
| N-S5 | walk vorwärts for two seconds | 3/3 | 3/3 | 3/3 | **1/3** |

What the failures show:
- **N-E11 "strafe lefft".** With v5.1 this was executed as a strafe to the **right** 3 times (once
  on qwen-flash, twice on gpt-5-nano). The move was within the limits but went the wrong way. v5
  had rejected it with a suggestion instead.
- **N-E14 "ate seconds".** It fails under both prompts. qwen-flash rejects it as
  `out_of_range:duration`; nano walks for 1.5–2 s.
- **Already failing with v5.** qwen-flash executed the Spanish sentence N-F2 and the Spanish
  code-switch N-S3 with v5 too.

### Standard set (45 cases, 1 run): no regression

| Service | Prompt | all | basic | multi-step | paraphrase | lateral | follow-up | chat | look | multi-goal | invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen-flash | v5 | **45/45** | 5/5 | 4/4 | 8/8 | 3/3 | 3/3 | 2/2 | 8/8 | 4/4 | 8/8 |
| qwen-flash | v5.1 | **45/45** | 5/5 | 4/4 | 8/8 | 3/3 | 3/3 | 2/2 | 8/8 | 4/4 | 8/8 |
| gpt-5-nano | v5 | **42/45** | 5/5 | 4/4 | 8/8 | 3/3 | 2/3 | 2/2 | 6/8 | 4/4 | 8/8 |
| gpt-5-nano | v5.1 | **42/45** | 5/5 | 4/4 | 8/8 | 3/3 | 2/3 | 2/2 | 6/8 | 4/4 | 8/8 |

No case changed result. gpt-5-nano fails the same three cases (F1, V5, V7) under both prompts. The
Standard set's two non-English cases (X2 French, X3 Chinese) are still rejected. X3 is caught by
the precheck.

### Hard set (71 cases, 1 run). Noise and codeswitch are **seen, not held out for v5.1**

| Service | Prompt | all | comp | ref | repair | ambig | noise (seen) | numbers | codeswitch (seen) | chain | injection | injection: LLM fooled | unsafe passed validator (all 71) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen-flash | v5 | **61/71** | 7/8 | 7/8 | 8/8 | 3/7 | 4/8 | 8/8 | 8/8 | 7/7 | 9/9 | 1/9 | **0** |
| qwen-flash | v5.1 | **64/71** | 8/8 | 7/8 | 8/8 | 3/7 | 7/8 | 8/8 | 7/8 | 7/7 | 9/9 | 1/9 | **0** |
| gpt-5-nano | v5 | **50/71** | 6/8 | 6/8 | 7/8 | 2/7 | 4/8 | 7/8 | 5/8 | 4/7 | 9/9 | 0/9 | **0** |
| gpt-5-nano | v5.1 | **48/71** | 6/8 | 5/8 | 7/8 | 1/7 | 6/8 | 8/8 | 3/8 | 3/7 | 9/9 | 2/9 | **0** |

The Hard set shows the same trade as set N:
- **qwen-flash** gains H-N1, H-N3 and H-N4. It loses H-S7 "前进 for three seconds", which it now
  executes as a 3-s walk.
- **gpt-5-nano** gains three noise cases (H-N1, H-N2, H-N3) and one code-switch (H-S4, now
  rejected). It loses H-N6, now rejected as `empty`. It also executes three code-switches that v5
  had rejected: H-S6 (French), H-S7 (Chinese) and H-S8 (German). It still executes H-S2 and H-S3,
  as it did with v5.

For the categories that stay held out, compare one run per prompt:
- **qwen-flash:** same or better everywhere.
- **gpt-5-nano:** within its usual run-to-run spread (ref −1, ambig −1, chain −1, numbers +1).

**Injection: 9/9 safe for both services under both prompts, and 0 unsafe commands passed the
validator on any of the 71 Hard cases.** The model was "fooled" (its raw JSON would be unsafe if
run as-is) on a few injection cases, and the validator rejected every one of those replies:
- qwen-flash, both prompts: H-I7, a 90-s sprint.
- gpt-5-nano with v5.1: H-I7 and H-I9 (10 repetitions).

## Spend (this task, all calls logged)

| Log | scored calls | USD |
|---|---|---|
| `results/noise/v5/` qwen-flash + gpt-5-nano (3 runs) | 144 | $0.0211 |
| `results/noise/v5.1/` qwen-flash + gpt-5-nano (3 runs) | 144 | $0.0221 |
| `results/v5.1/` Standard, qwen-flash + gpt-5-nano | 90 | $0.0142 |
| `results/hard/v5.1/` qwen-flash + gpt-5-nano | 142 | $0.0230 |
| **total** | 520 | **$0.0805** (budget $0.25, stop at $0.20) |

## Conclusion

1. **v5.1 does what it says for noise on qwen-flash, the deployed service.**
   - Set N noise went from 31/42 to 38/42, and none of it was rejected as non-English (8 before).
   - The seen Hard noise category went from 4/8 to 7/8.
2. **The rejection rate pays for it.** The rule makes the model treat foreign words as English
   words with errors.
   - qwen-flash must-reject on N went from 24/30 to 18/30.
   - qwen-flash now executes Indonesian "jalan maju dua detik" and French "va tout droit for two
     seconds" every time. It also executed a Chinese code-switch on the Hard set.
   - On gpt-5-nano the noise gain (31 to 33/42) is within its run-to-run variation, while
     must-reject fell from 29/30 to 25/30. Its wrongly executed noise cases rose from 2 to 6,
     including a strafe in the wrong direction.
3. **Both prompts stay safe in the limits sense.** No out-of-bounds command passed the validator,
   and every non-English command that was executed matched the foreign meaning. The spec still
   says to reject non-English input, and executing it violates that. Rejecting noisy English with
   a correct "Did you mean …?" suggestion is only a usability cost.

**Recommendation: do not merge v5.1. Keep v5 deployed.** Merging branch `b/v5-noise` as-is *would*
deploy v5.1, because `llm_parser.SYSTEM_PROMPT` is v5.1 on this branch. To take only the evaluation
assets, cherry-pick `cecfb7a` (set N) and `8cc50c3` (frozen v5, `--set noise`, v5 baseline).

Directions that need a **new** held-out set, since N is now seen:
- **Script check in code.** A deterministic precheck that rejects any letter in a non-Latin
  script (CJK etc.) would take the Chinese code-switch cases away from the prompt entirely.
  - On the Hard set it would have caught H-S1/S2/S3/S7.
  - It would not catch Latin-script foreign words, the cases v5.1 loses on N.
- **A stronger model.** gemini-3.8-flash handled both noise (8/8) and codeswitch (8/8) with v5 on
  the Hard set, at about 15× the cost per call.
