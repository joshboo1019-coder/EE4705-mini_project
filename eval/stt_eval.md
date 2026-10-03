# Bonus — speech input (STT) evaluation

Session `20261002-224741`. **One speaker** (the project author), the laptop's built-in microphone, room noise about −41 dBFS, push-to-talk recorder from `dialogue/speech_input.py`. STT: faster-whisper `small`, local on the GPU (CUDA float16); parser: `qwen-flash` with the current prompt, no history. Every transcript is scored with the same checker as the typed Task 3 eval (`eval/task3_eval.py`). The recordings stay local in `eval/results/stt/20261002-224741/` (git-ignored); per-utterance metrics are in `eval/results/stt/20261002-224741.jsonl`.

Scoring: English rows pass if the parsed command passes the typed-eval checker; X1 ("fly to the roof") passes if it is transcribed and then rejected by the parser. Non-English rows (X2 French, X3 Mandarin) are scored only as *rejected as non-English: yes/no* and are left out of the WER.

## Summary

- English utterances handled correctly: **9/10**
- Non-English rejected as non-English: **2/2**
- English word error rate (pooled over 10 utterances): **6.9%** (4 word errors / 58 reference words; digits are normalised, so "3 seconds" = "three seconds")
- English utterances identified as English: **10/10**, p = 0.82–0.98
- Latency, median: STT **0.10 s**; STT + LLM **0.46 s** (over the 11 utterances that reached the LLM). Measured from the end of recording, so it excludes the 1 s of silence the recorder waits for.

## Per utterance

| Id | Reference | Transcript | lang / p | WER | Parsed OK | STT s | STT+LLM s |
|---|---|---|---|---|---|---|---|
| B1 | walk forward for three seconds | Walk forward for 3 seconds. | en / 0.96 | 0% | ✅ move | 0.12 | 0.94 |
| B3 | turn right 45 degrees | Turn right 45 degrees | en / 0.93 | 0% | ✅ turn | 0.10 | 0.43 |
| B5 | go to the green chair | Go to the green chair | en / 0.92 | 0% | ✅ goto_object | 0.09 | 0.46 |
| M1 | walk forward for three seconds, then turn back | Walk forward for 3 seconds, then turn back. | en / 0.98 | 0% | ✅ move, turn | 0.13 | 0.73 |
| M3 | back up for two seconds and then turn right | Back up for two seconds and then turn right | en / 0.98 | 0% | ✅ move, turn | 0.11 | 0.69 |
| P3 | do a U-turn | Do a U turn | en / 0.82 | 0% | ✅ turn | 0.09 | 0.39 |
| P5 | move ahead slowly for four seconds | Move ahead slowly for 4 seconds. | en / 0.98 | 0% | ✅ move | 0.09 | 0.58 |
| L1 | sidestep to your left for two seconds | Side step to a left for two seconds | en / 0.98 | 43% | ✅ move | 0.11 | 0.59 |
| L2 | shuffle right for one second | Shuffle rights for one second | en / 0.95 | 20% | ❌ rejected: empty | 0.10 | 0.37 |
| X1 | fly to the roof | fly to the roof | en / 0.96 | 0% | ✅ rejected: impossible:fly | 0.11 | 0.40 |
| X2 | avancez tout droit (French) | Avian's Toad droid | en / 0.55 | n/a | rejected as non-English: yes (by LLM) | 0.10 | 0.40 |
| X3 | 向前走三秒 (Mandarin) | 向前走三秒 | zh / 1.00 | n/a | rejected as non-English: yes (by language ID) | 0.09 | 0.09 (no LLM) |

## Failure analysis

- **L2, the only English failure, is a parser failure triggered by a one-letter STT error.** Whisper heard
  "Shuffle **rights** for one second", and qwen-flash rejected that as `empty` in 2 of 2 offline retries,
  while it parses "Shuffle right for one second" correctly (vy −0.8, 1 s) in 2 of 2. Larger STT errors were
  harmless: L1 came out as "Side step to a left for two seconds" (WER 43%) and still parsed to the correct
  left sidestep. So the end-to-end weak point is the parser's tolerance of near-miss words, not the WER itself.
- **Language ID was reliable for English and Mandarin, but not for short French.** All 10 English utterances
  were identified as `en` (p ≥ 0.82), so the planned stricter rule (reject only at p ≥ 0.8, re-transcribe
  0.5–0.8 as English) was not needed and was not applied. Mandarin was caught by language ID (zh, p = 1.00)
  without an LLM call. French "avancez tout droit" was identified as **English** (p = 0.55) and transcribed
  as "Avian's Toad droid"; it was still rejected as `non-English`, but only by the LLM. That's a lucky
  rather than a robust path for a 3-word phrase.
- **Latency is dominated by the LLM**, not STT: whisper small on the GPU takes about 0.1 s, the parse about
  0.4–0.8 s more. A user also waits for the recorder's 1 s silence timeout after speaking.

## Follow-up: `initial_prompt` with the command vocabulary (adopted)

After the session above, faster-whisper's `initial_prompt` was set to a short command vocabulary
(`speech_input.WHISPER_PROMPT`: walk, turn, left, right, forward, back, sidestep, shuffle, seconds, degrees,
chair, ball, stop sign, green, red, orange). The same 12 saved WAVs were re-transcribed offline: no
re-recording and no LLM calls, the same model and decoding settings, and only `initial_prompt` changed. The
tables above are the original run, without the prompt.

| Id | Without prompt | With prompt | WER before → after | lang / p (both) |
|---|---|---|---|---|
| L1 | Side step to a left for two seconds | sidestep to a left for 2 seconds | 43% → 14% | en / 0.98 |
| L2 | Shuffle rights for one second | shuffle right for one second | 20% → **0%** | en / 0.95 |
| X2 (French) | Avian's Toad droid | avians toward droids | n/a | en / **0.56** (unchanged) |
| the other 9 | same words; only the casing, punctuation and number format differ (M3 "two" → "2") | | 0% → 0% | unchanged |

- **Pooled English WER: 6.9% → 1.7%** (4 → 1 word errors / 58). The one error left is L1's "to a left" vs
  "to your left". No utterance got worse. STT latency is unchanged (about 0.1 s).
- **L2:** the transcript is now exactly the reference. The parser accepted this string ("Shuffle right for one
  second") 2 of 2 times in the earlier offline retries, so L2 should now pass end-to-end. That wasn't re-run
  here, because this check was offline only.
- **Language probabilities are identical** for all 12 clips. faster-whisper detects the language before
  decoding, and that step doesn't use the prompt. So the French clip is still identified as English
  (p = 0.56), and its rejection still relies on the LLM. The prompt doesn't fix that weak path.
- Caveat: a vocabulary prompt can bias Whisper towards those words on noise or near-silence. The VAD filter
  limits that, but this 12-clip set from one speaker doesn't test it.
