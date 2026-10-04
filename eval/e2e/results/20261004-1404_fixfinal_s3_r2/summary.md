# e2e run `20261004-1404_fixfinal_s3_r2`

Commit: `7791d5d` on `fix/final`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1404_fixfinal_s3_r2/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 32/32 (target 22) | FAIL:stop_verification | 24.6 | None | 0.64 | ❌ | ❌ | ✅ | ❌ | ❌ | 0 / 0 / 0 | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 52/59 (target 36) | SUCCESS | 26.9 | 0.76 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 8 / 0 (red_stop sign) | – |
| 03 | `go to the green chair` | ✅ | ❌ | 63/63 (target 28) | SUCCESS | 16.1 | 0.45 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 61/61 (target 30) | FAIL:stop_verification | 33.3 | None | 0.64 | ❌ | ❌ | ✅ | ❌ | ❌ | 0 / 0 / 0 | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 10.9 | None | 3.77 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 11.0 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 36/41 (target 22) | SUCCESS | 16.5 | 0.72 | 0.62 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 31/31 (target 28) | SUCCESS | 16.0 | 0.46 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 11.0 | None | 1.26 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 34/34 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 5/10** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
