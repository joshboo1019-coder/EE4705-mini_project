# e2e run `20261004-1725_p2b_gate_r1`

Commit: `0b91b6f` on `iter/avoid`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1725_p2b_gate_r1/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 36/36 (target 26) | SUCCESS | 21.8 | 0.51 | 0.61 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 66/74 (target 50) | SUCCESS | 31.6 | 0.73 | 0.58 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 15 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ✅ | 87/92 (target 25) | FAIL:target_not_found | 79.0 | None | 0.56 | ❌ | ❌ | ✅ | ❌ | ❌ | 274 / 0 / 0 (green_chair) | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 59/59 (target 29) | SUCCESS | 26.8 | 0.42 | 0.56 | ✅ | ✅ | ✅ | ✅ | ✅ | 62 / 0 / 0 (red_chair) | – |
| 05 | `go to the yellow stop sign` | ✅ | ❌ | 20/22 (target 2) | SUCCESS | 24.0 | 0.62 | 0.6 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 22/27 (target 0) | SUCCESS | 37.0 | 0.68 | 0.8 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 28/38 (target 21) | SUCCESS | 16.5 | 0.75 | 0.65 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 24/24 (target 21) | SUCCESS | 26.8 | 0.46 | 0.7 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ❌ | 5/5 (target 0) | SUCCESS | 10.0 | 0.7 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/34 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 9/10** · runs with target contact: 2

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
