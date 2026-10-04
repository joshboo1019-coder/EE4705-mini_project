# e2e run `20261004-1745_p2b_gate_r3`

Commit: `0b91b6f` on `iter/avoid`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1745_p2b_gate_r3/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 34/34 (target 24) | SUCCESS | 39.5 | 0.51 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 69/77 (target 53) | SUCCESS | 32.3 | 0.75 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 03 | `go to the green chair` | ✅ | ❌ | 75/75 (target 31) | SUCCESS | 17.9 | 0.47 | 0.7 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 61/61 (target 30) | SUCCESS | 28.6 | 0.52 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 05 | `go to the yellow stop sign` | ✅ | ❌ | 20/21 (target 0) | SUCCESS | 18.5 | 0.68 | 0.73 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 44/53 (target 0) | SUCCESS | 60.6 | 0.67 | 0.83 | ✅ | ✅ | ❌ | ✅ | ❌ | 0 / 30 / 0 (green_chair) | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 30/35 (target 21) | SUCCESS | 16.7 | 0.72 | 0.62 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 33/33 (target 28) | SUCCESS | 15.5 | 0.45 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 32/32 (target 1) | FAIL:timeout | 120.1 | None | 0.55 | ❌ | ❌ | ✅ | ❌ | ❌ | 19 / 0 / 0 (red_stop sign) | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/34 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 8/10** · runs with target contact: 1

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
