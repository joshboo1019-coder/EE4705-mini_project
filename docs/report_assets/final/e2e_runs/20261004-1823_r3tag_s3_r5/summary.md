# e2e run `20261004-1823_r3tag_s3_r5`

Commit: `0532ff0` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1823_r3tag_s3_r5/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 30/30 (target 20) | SUCCESS | 26.1 | 0.55 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 52/58 (target 34) | SUCCESS | 29.7 | 0.72 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 1 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ❌ | 57/57 (target 27) | SUCCESS | 21.3 | 0.47 | 0.7 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 56/56 (target 29) | SUCCESS | 26.5 | 0.46 | 0.58 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/24 (target 0) | FAIL:target_not_found | 11.0 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 10.9 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 30/35 (target 19) | SUCCESS | 19.9 | 0.69 | 0.59 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 27/27 (target 25) | SUCCESS | 19.2 | 0.44 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 11.0 | None | 1.28 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/34 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 7/10** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
