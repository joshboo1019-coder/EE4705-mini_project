# e2e run `20261004-1732_p2b_gate_r2`

Commit: `0b91b6f` on `iter/avoid`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1732_p2b_gate_r2/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 36/36 (target 27) | SUCCESS | 20.7 | 0.46 | 0.57 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 74/81 (target 51) | SUCCESS | 35.6 | 0.73 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 03 | `go to the green chair` | ✅ | ❌ | 79/79 (target 34) | SUCCESS | 19.1 | 0.46 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 55/55 (target 30) | SUCCESS | 30.4 | 0.5 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 05 | `go to the yellow stop sign` | ✅ | ❌ | 23/24 (target 0) | SUCCESS | 15.8 | 0.67 | 0.72 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 21/26 (target 0) | SUCCESS | 36.5 | 0.68 | 0.86 | ✅ | ✅ | ❌ | ✅ | ❌ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 40/47 (target 25) | SUCCESS | 19.6 | 0.75 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 28/28 (target 25) | SUCCESS | 14.8 | 0.48 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ❌ | 4/4 (target 0) | SUCCESS | 9.6 | 0.7 | 0.72 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/34 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 9/10** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
