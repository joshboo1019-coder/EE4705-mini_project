# e2e run `20261004-1337_premerge_gate`

Commit: `3520519` on `release/merge`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1337_premerge_gate/` (not recorded).

## S2 — Task 3 (Video_Task3 script a–g, typed into main.py)

Pass: ✅ · turn errors [1.5, -1.1, -1.6] · fall ✅ · contacts none · max tilt 7.1° · clip –

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
| 01 | `go to the red chair` | ✅ | ✅ | 56/58 (target 23) | FAIL:target_not_found | 104.8 | None | 0.21 | ❌ | ❌ | ✅ | ❌ | ❌ | – |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 57/66 (target 40) | SUCCESS | 31.9 | 0.73 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | – |
| 03 | `go to the green chair` | ✅ | ❌ | 66/66 (target 31) | SUCCESS | 15.4 | 0.46 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 67/67 (target 36) | SUCCESS | 41.3 | 0.49 | 0.68 | ✅ | ✅ | ✅ | ✅ | ✅ | – |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/22 (target 0) | FAIL:target_not_found | 10.9 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 11.1 | None | 5.05 | ❌ | ❌ | ❌ | ❌ | ❌ | – |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 32/39 (target 20) | SUCCESS | 16.5 | 0.74 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 27/27 (target 25) | SUCCESS | 16.8 | 0.45 | 0.62 | ✅ | ✅ | ✅ | ✅ | ✅ | – |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 10.9 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | – |
| 10 | `go to the blue chair` | ✅ | ✅ | 35/35 (target 0) | FAIL:target_not_found | 11.0 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | – |

**S3 success: 6/10**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
