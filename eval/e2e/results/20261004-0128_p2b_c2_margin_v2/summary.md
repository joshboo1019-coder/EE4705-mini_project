# e2e run `20261004-0128_p2b_c2_margin_v2`

Commit: `2999c7b` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0128_p2b_c2_margin_v2/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 37/37 (target 28) | SUCCESS | 54.0 | 0.48 | 0.74 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0128_p2b_c2_margin_v2/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 51/57 (target 33) | SUCCESS | 28.3 | 0.72 | 0.61 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0128_p2b_c2_margin_v2/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 69/69 (target 30) | SUCCESS | 16.0 | 0.47 | 0.68 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0128_p2b_c2_margin_v2/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 61/61 (target 29) | FAIL:stop_verification | 25.2 | None | 0.59 | ❌ | ❌ | ✅ | ❌ | ❌ | `20261004-0128_p2b_c2_margin_v2/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 10.9 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0128_p2b_c2_margin_v2/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/10 (target 0) | FAIL:target_not_found | 10.8 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0128_p2b_c2_margin_v2/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 33/40 (target 21) | SUCCESS | 20.6 | 0.68 | 0.6 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0128_p2b_c2_margin_v2/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 27/27 (target 25) | SUCCESS | 21.6 | 0.48 | 0.7 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0128_p2b_c2_margin_v2/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 10.8 | None | 1.28 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0128_p2b_c2_margin_v2/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 35/35 (target 0) | FAIL:target_not_found | 10.9 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-0128_p2b_c2_margin_v2/S3_10.mp4` |

**S3 success: 6/10**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
