# e2e run `20261004-0304_final_rep2`

Commit: `4baf6c6` on `b/overnight-all`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0304_final_rep2/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 46/46 (target 36) | SUCCESS | 85.4 | 0.48 | 0.87 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0304_final_rep2/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 72/83 (target 55) | SUCCESS | 39.5 | 0.75 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0304_final_rep2/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 72/72 (target 32) | SUCCESS | 17.0 | 0.48 | 0.7 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0304_final_rep2/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 61/61 (target 30) | FAIL:stop_verification | 24.8 | None | 0.6 | ❌ | ❌ | ✅ | ❌ | ❌ | `20261004-0304_final_rep2/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 10.8 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0304_final_rep2/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 10.9 | None | 5.05 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0304_final_rep2/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 32/41 (target 20) | SUCCESS | 20.2 | 0.71 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0304_final_rep2/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 28/28 (target 26) | SUCCESS | 15.8 | 0.44 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0304_final_rep2/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 10.9 | None | 1.26 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0304_final_rep2/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 30/30 (target 0) | FAIL:target_not_found | 10.8 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-0304_final_rep2/S3_10.mp4` |

**S3 success: 5/10**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
