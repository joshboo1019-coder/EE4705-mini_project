# e2e run `20261004-1455_iter1_s3_r1`

Commit: `886871b` on `iter/close-range-c1`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1455_iter1_s3_r1/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 28/28 (target 18) | SUCCESS | 29.6 | 0.5 | 0.6 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 55/61 (target 38) | SUCCESS | 31.0 | 0.75 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 7 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ❌ | 58/58 (target 29) | SUCCESS | 15.3 | 0.48 | 0.73 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 59/59 (target 29) | SUCCESS | 25.6 | 0.46 | 0.61 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/24 (target 0) | FAIL:target_not_found | 10.9 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 06 | `` | ❌ | – | None/None (target None) | None | None | None | None | – | – | – | – | ❌ | – | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 32/37 (target 21) | SUCCESS | 16.4 | 0.72 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 25/25 (target 0) | FAIL:target_not_found | 10.9 | None | 2.48 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 10.9 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/34 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 6/10** · runs with target contact: 0

## Run notes

- Crashed / never ready: ['S3_06']
- Clips deleted by the frame check: none
