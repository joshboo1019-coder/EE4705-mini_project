# e2e run `20261004-1438_tag_s3_r4`

Commit: `1b95477` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1438_tag_s3_r4/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 30/30 (target 21) | SUCCESS | 22.4 | 0.55 | 0.68 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 59/68 (target 34) | SUCCESS | 31.6 | 0.75 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 1 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ❌ | 73/73 (target 32) | SUCCESS | 17.4 | 0.46 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 68/68 (target 38) | SUCCESS | 101.5 | 0.54 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | 68 / 0 / 0 (red_chair) | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/20 (target 0) | FAIL:target_not_found | 10.9 | None | 3.79 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 10.9 | None | 5.05 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 30/36 (target 22) | SUCCESS | 16.5 | 0.74 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 28/28 (target 24) | SUCCESS | 18.6 | 0.47 | 0.65 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 10.9 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 29/34 (target 0) | FAIL:target_not_found | 10.9 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 7/10** · runs with target contact: 1

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
