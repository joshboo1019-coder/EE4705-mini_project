# e2e run `20261004-1206_morning_merge`

Commit: `f2bd152` on `b/overnight-all`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1206_morning_merge/` (recorded).

## S2 — Task 3 (Video_Task3 script a–g, typed into main.py)

Pass: ✅ · turn errors [1.4, -0.9, -1.5] · fall ✅ · contacts none · max tilt 7.2° · clip `20261004-1206_morning_merge/S2_video_task3.mp4`

| Step | Typed | [CMD] line | OK |
|---|---|---|---|
| a | `turn left 90 degrees` | `[CMD] actions=turn(90 deg) n=1` | ✅ |
| b | `walk forward for three seconds, then turn back` | `[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2` | ✅ |
| c | `walk forward for two seconds, then turn right 90 degrees` | `[CMD] actions=move(vx=0.8, 2.0 s), turn(-90 deg) n=2` | ✅ |
| d | `sidestep to your left for two seconds` | `[CMD] actions=move(vx=0, vy=0.8, 2.0 s) n=1` | ✅ |
| e | `do that again, but slower` | `[CMD] actions=move(vx=0, vy=0.3, 2.0 s) n=1` | ✅ |
| f | `fly to the roof` | `[CMD] rejected reason=impossible:fly` | ✅ |
| g | `avancez tout droit` | `[CMD] rejected reason=non-English` | ✅ |

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 33/33 (target 23) | FAIL:stop_verification | 16.7 | None | 0.64 | ❌ | ❌ | ✅ | ❌ | ❌ | `20261004-1206_morning_merge/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 54/61 (target 34) | SUCCESS | 31.6 | 0.75 | 0.62 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1206_morning_merge/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 59/59 (target 26) | SUCCESS | 16.5 | 0.47 | 0.71 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1206_morning_merge/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 61/61 (target 30) | SUCCESS | 27.3 | 0.46 | 0.59 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1206_morning_merge/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 10.8 | None | 3.77 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-1206_morning_merge/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 10.8 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-1206_morning_merge/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 38/48 (target 24) | SUCCESS | 16.6 | 0.76 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1206_morning_merge/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 29/29 (target 26) | SUCCESS | 17.9 | 0.47 | 0.65 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1206_morning_merge/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 10.9 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-1206_morning_merge/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 35/35 (target 0) | FAIL:target_not_found | 10.8 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-1206_morning_merge/S3_10.mp4` |

**S3 success: 6/10**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
