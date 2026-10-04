# e2e run `20261004-1216_no_gt_height`

Commit: `3713647` on `assist/no-gt-height`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1216_no_gt_height/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 40/40 (target 30) | SUCCESS | 51.7 | 0.48 | 0.76 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1216_no_gt_height/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 55/63 (target 32) | SUCCESS | 31.3 | 0.75 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1216_no_gt_height/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 63/63 (target 28) | SUCCESS | 15.3 | 0.47 | 0.72 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1216_no_gt_height/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 60/60 (target 29) | FAIL:stop_verification | 23.4 | None | 0.58 | ❌ | ❌ | ✅ | ❌ | ❌ | `20261004-1216_no_gt_height/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 10.9 | None | 3.77 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-1216_no_gt_height/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 11.0 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-1216_no_gt_height/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 34/40 (target 20) | SUCCESS | 24.7 | 0.7 | 0.59 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1216_no_gt_height/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 26/26 (target 24) | SUCCESS | 18.2 | 0.47 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1216_no_gt_height/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 11.0 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-1216_no_gt_height/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 35/37 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-1216_no_gt_height/S3_10.mp4` |

**S3 success: 6/10**

## S7 — blue chair on the stairs (C's stairs sequence, default scene)

| Mission | [FOUND] | true d | range pairs | true − est (first / last / mean) | Climb | Pass | Clip |
|---|---|---|---|---|---|---|---|
| `[MISSION] status=SUCCESS` | `[FOUND] class=chair color=blue t=11.3 s d=0.95 m` | 0.95 | 20 | 0.42 / 0.41 / 0.42 | `climb outcome='completed'  pose: x=0.58 y=1.99 yaw=14.8 trunk_z=0.328 m` | ❌ | `20261004-1216_no_gt_height/S7_blue_chair_stairs.mp4` |

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
