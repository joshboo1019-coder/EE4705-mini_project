# e2e run `20261004-0317_final_rep3`

Commit: `4baf6c6` on `b/overnight-all`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0317_final_rep3/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 66/67 (target 38) | SUCCESS | 106.6 | 0.54 | 0.77 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0317_final_rep3/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 65/72 (target 43) | SUCCESS | 27.6 | 0.75 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0317_final_rep3/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 61/61 (target 28) | SUCCESS | 15.2 | 0.45 | 0.7 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0317_final_rep3/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 62/62 (target 29) | FAIL:stop_verification | 23.2 | None | 0.6 | ❌ | ❌ | ✅ | ❌ | ❌ | `20261004-0317_final_rep3/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 10.8 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0317_final_rep3/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 10.9 | None | 5.05 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0317_final_rep3/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 39/44 (target 22) | SUCCESS | 16.5 | 0.74 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0317_final_rep3/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 32/32 (target 30) | SUCCESS | 15.4 | 0.52 | 0.71 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0317_final_rep3/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/19 (target 0) | FAIL:target_not_found | 10.8 | None | 1.28 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0317_final_rep3/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 35/35 (target 0) | FAIL:target_not_found | 10.9 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-0317_final_rep3/S3_10.mp4` |

**S3 success: 6/10**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
