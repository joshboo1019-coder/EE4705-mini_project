# e2e run `20261004-0138_stopsign_eval`

Commit: `4d7f147` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0138_stopsign_eval/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 70/79 (target 21) | FAIL:timeout | 125.0 | None | 0.24 | ❌ | ❌ | ✅ | ❌ | ❌ | `20261004-0138_stopsign_eval/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 112/146 (target 48) | SUCCESS | 36.7 | 0.74 | 0.56 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0138_stopsign_eval/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 60/60 (target 27) | SUCCESS | 15.2 | 0.46 | 0.68 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0138_stopsign_eval/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 59/60 (target 29) | FAIL:stop_verification | 22.6 | None | 0.56 | ❌ | ❌ | ✅ | ❌ | ❌ | `20261004-0138_stopsign_eval/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 42/65 (target 26) | SUCCESS | 23.2 | 0.54 | 0.93 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0138_stopsign_eval/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 11.0 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0138_stopsign_eval/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 58/81 (target 24) | SUCCESS | 45.7 | 0.69 | 0.55 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0138_stopsign_eval/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 33/33 (target 18) | SUCCESS | 15.8 | 0.45 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0138_stopsign_eval/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 74/78 (target 25) | FAIL:timeout | 123.7 | None | 1.24 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0138_stopsign_eval/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 31/31 (target 0) | FAIL:target_not_found | 10.9 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-0138_stopsign_eval/S3_10.mp4` |

**S3 success: 5/10**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
