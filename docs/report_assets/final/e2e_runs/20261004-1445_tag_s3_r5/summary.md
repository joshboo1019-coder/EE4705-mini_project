# e2e run `20261004-1445_tag_s3_r5`

Commit: `1b95477` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1445_tag_s3_r5/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 52/52 (target 24) | FAIL:target_not_found | 80.6 | None | 0.65 | ❌ | ❌ | ✅ | ❌ | ❌ | 27 / 0 / 0 (red_chair) | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 64/74 (target 46) | FAIL:stop_verification | 32.9 | 0.82 | 0.69 | ✅ | ❌ | ✅ | ❌ | ❌ | 0 / 39 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ❌ | 61/61 (target 28) | SUCCESS | 15.9 | 0.47 | 0.72 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 59/59 (target 29) | SUCCESS | 24.8 | 0.47 | 0.61 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/24 (target 0) | FAIL:target_not_found | 10.9 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/11 (target 0) | FAIL:target_not_found | 10.9 | None | 5.03 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 36/41 (target 19) | SUCCESS | 24.3 | 0.69 | 0.59 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 24/24 (target 22) | SUCCESS | 19.2 | 0.45 | 0.68 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/17 (target 0) | FAIL:target_not_found | 10.9 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/34 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 5/10** · runs with target contact: 1

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
