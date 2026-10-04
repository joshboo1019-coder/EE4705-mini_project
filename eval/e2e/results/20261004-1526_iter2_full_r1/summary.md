# e2e run `20261004-1526_iter2_full_r1`

Commit: `28bb091` on `iter/stopsign-plate`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1526_iter2_full_r1/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 38/38 (target 24) | FAIL:timeout | 121.5 | None | 1.6 | ❌ | ❌ | ❌ | ❌ | ❌ | 18 / 0 / 0 (red_chair) | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 65/75 (target 48) | SUCCESS | 32.8 | 0.76 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 58 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ❌ | 60/60 (target 27) | SUCCESS | 15.2 | 0.44 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 61/61 (target 29) | FAIL:stop_verification | 26.7 | None | 0.61 | ❌ | ❌ | ✅ | ❌ | ❌ | 0 / 0 / 0 | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 36/37 (target 1) | SUCCESS | 95.0 | 0.7 | 0.6 | ✅ | ✅ | ✅ | ✅ | ✅ | 3 / 0 / 0 (yellow_stop sign) | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 11.0 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 36/41 (target 24) | SUCCESS | 16.5 | 0.75 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 31/31 (target 27) | SUCCESS | 25.2 | 0.47 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ❌ | 3/3 (target 0) | SUCCESS | 5.9 | 0.66 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/34 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 7/10** · runs with target contact: 2

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
