# e2e run `20261004-0111_p2a_task4_via_main`

Commit: `8fde6cc` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0111_p2a_task4_via_main/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 33/33 (target 24) | SUCCESS | 13.2 | 0.71 | 0.84 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0111_p2a_task4_via_main/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 72/86 (target 49) | SUCCESS | 34.7 | 0.75 | 0.68 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0111_p2a_task4_via_main/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 57/57 (target 27) | SUCCESS | 14.1 | 0.73 | 0.96 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0111_p2a_task4_via_main/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 60/60 (target 30) | SUCCESS | 19.8 | 0.75 | 0.88 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0111_p2a_task4_via_main/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 11.0 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0111_p2a_task4_via_main/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 11.4 | None | 5.03 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0111_p2a_task4_via_main/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 34/40 (target 22) | SUCCESS | 16.5 | 0.77 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0111_p2a_task4_via_main/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 16/16 (target 16) | SUCCESS | 14.4 | 0.7 | 0.89 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0111_p2a_task4_via_main/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 10.8 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0111_p2a_task4_via_main/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 30/30 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-0111_p2a_task4_via_main/S3_10.mp4` |

**S3 success: 3/10**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
