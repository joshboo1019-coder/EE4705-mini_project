# e2e run `20261004-1357_fixfinal_s3_r1`

Commit: `7791d5d` on `fix/final`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1357_fixfinal_s3_r1/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 58/58 (target 23) | FAIL:target_not_found | 88.1 | None | 0.58 | ❌ | ❌ | ✅ | ❌ | ❌ | 179 / 0 / 0 (red_chair) | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 52/58 (target 34) | SUCCESS | 27.7 | 0.75 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 1 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ❌ | 63/63 (target 30) | SUCCESS | 16.2 | 0.46 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 58/58 (target 28) | FAIL:stop_verification | 27.2 | None | 0.63 | ❌ | ❌ | ✅ | ❌ | ❌ | 0 / 0 / 0 | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/22 (target 0) | FAIL:target_not_found | 11.0 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 10.9 | None | 5.05 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 34/44 (target 22) | SUCCESS | 16.5 | 0.75 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 21/21 (target 21) | SUCCESS | 19.9 | 0.44 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 11.0 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/35 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 5/10** · runs with target contact: 1

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
