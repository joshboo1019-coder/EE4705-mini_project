# e2e run `20261004-1716_rc_s3_r1`

Commit: `fa17c08` on `rc`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1716_rc_s3_r1/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 31/31 (target 21) | FAIL:timeout | 127.5 | None | 0.24 | ❌ | ❌ | ✅ | ❌ | ❌ | 830 / 0 / 0 (red_chair) | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 70/80 (target 53) | SUCCESS | 37.9 | 0.75 | 0.61 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 73 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ❌ | 68/68 (target 29) | FAIL:stop_verification | 25.4 | None | 0.72 | ❌ | ❌ | ✅ | ❌ | ❌ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 57/57 (target 27) | SUCCESS | 29.2 | 0.5 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/20 (target 0) | FAIL:target_not_found | 11.0 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/10 (target 0) | FAIL:target_not_found | 11.0 | None | 5.05 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 31/37 (target 20) | SUCCESS | 20.3 | 0.68 | 0.59 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 30/30 (target 26) | SUCCESS | 16.5 | 0.44 | 0.62 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 11.0 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/38 (target 0) | FAIL:target_not_found | 10.9 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 5/10** · runs with target contact: 1

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
