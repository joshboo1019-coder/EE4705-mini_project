# e2e run `20261004-1856_r7_s2_r1`

Commit: `15ae7db` on `fix/unseen-goto`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1856_r7_s2_r1/` (not recorded).

## S2 — Task 3 (Video_Task3 script a–g, typed into main.py)

Pass: ✅ · turn errors [1.3, 1.9, 1.2, 1.5, 1.5, 2.0, 1.8, 1.8, -1.8, -1.3] · fall ✅ · contacts none · max tilt 7.1° · clip –

| Step | Typed | [CMD] line | OK |
|---|---|---|---|
| a | `turn left 90 degrees` | `[CMD] actions=turn(90 deg) n=1` | ✅ |
| b | `walk forward for three seconds, then turn back` | `[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2` | ✅ |
| c | `walk forward for two seconds, then turn right 90 degrees` | `[CMD] actions=move(vx=0.8, 2.0 s), turn(-90 deg) n=2` | ✅ |
| d | `sidestep to your left for two seconds` | `[CMD] actions=move(vx=0, vy=0.8, 2.0 s) n=1` | ✅ |
| e | `do that again, but slower` | `[CMD] actions=move(vx=0, vy=0.3, 2.0 s) n=1` | ✅ |
| f | `fly to the roof` | `[CMD] rejected reason=impossible:fly` | ✅ |
| g | `avancez tout droit` | `[CMD] rejected reason=non-English` | ✅ |

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
