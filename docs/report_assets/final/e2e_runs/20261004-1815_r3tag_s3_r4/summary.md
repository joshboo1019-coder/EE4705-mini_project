# e2e run `20261004-1815_r3tag_s3_r4`

Commit: `0532ff0` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1815_r3tag_s3_r4/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 29/29 (target 19) | SUCCESS | 26.3 | 0.55 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 53/61 (target 35) | SUCCESS | 31.3 | 0.74 | 0.62 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 1 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ❌ | 60/60 (target 28) | SUCCESS | 15.4 | 0.45 | 0.72 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 68/68 (target 33) | SUCCESS | 79.4 | 0.55 | 0.86 | ✅ | ✅ | ❌ | ✅ | ❌ | 70 / 0 / 0 (red_chair) | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 10.9 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/10 (target 0) | FAIL:target_not_found | 10.9 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 33/40 (target 21) | SUCCESS | 16.6 | 0.73 | 0.62 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 21/21 (target 16) | SUCCESS | 20.2 | 0.46 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 11.0 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 29/29 (target 0) | FAIL:target_not_found | 10.9 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 6/10** · runs with target contact: 1

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
