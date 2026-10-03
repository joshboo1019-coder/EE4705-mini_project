# e2e run `20261004-0101_baseline`

Commit: `32c6f78` on `b/overnight-all`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0101_baseline/` (recorded).

## S1 — Task 2 skills

| Scenario | Result | Pass | Fall / contacts | Clip |
|---|---|---|---|---|
| closed | max \|error\| 1.9° | ✅ | ✅ fall, 0 contacts | `20261004-0101_baseline/S1_closed.mp4` |
| open | mean \|error\| 79.6° | ✅ | ✅ fall, 0 contacts | `20261004-0101_baseline/S1_open.mp4` |
| move | distance 2.24 m | ✅ | ✅ fall, 0 contacts | `20261004-0101_baseline/S1_move.mp4` |

```
[S1] mode=closed target=45 trial=1 achieved=43.2 error=-1.8 deg t=1.1 s
[S1] mode=closed target=45 trial=2 achieved=43.6 error=-1.4 deg t=1.2 s
[S1] mode=closed target=45 trial=3 achieved=43.7 error=-1.3 deg t=1.2 s
[S1] mode=closed target=90 trial=1 achieved=88.8 error=-1.2 deg t=2.5 s
[S1] mode=closed target=90 trial=2 achieved=88.1 error=-1.9 deg t=2.4 s
[S1] mode=closed target=90 trial=3 achieved=88.7 error=-1.3 deg t=2.5 s
[S1] mode=closed target=180 trial=1 achieved=181.9 error=+1.9 deg t=3.8 s
[S1] mode=closed target=180 trial=2 achieved=181.6 error=+1.6 deg t=3.8 s
[S1] mode=closed target=180 trial=3 achieved=181.9 error=+1.9 deg t=3.8 s
```
```
[S1] mode=open target=45 trial=1 achieved=10.8 error=-34.2 deg t=1.3 s wz=0.6 duration=0.75 s
[S1] mode=open target=45 trial=2 achieved=11.2 error=-33.8 deg t=1.3 s wz=0.6 duration=0.75 s
[S1] mode=open target=45 trial=3 achieved=10.7 error=-34.3 deg t=1.3 s wz=0.6 duration=0.75 s
[S1] mode=open target=90 trial=1 achieved=21.9 error=-68.1 deg t=2.0 s wz=0.6 duration=1.50 s
[S1] mode=open target=90 trial=2 achieved=20.9 error=-69.1 deg t=2.0 s wz=0.6 duration=1.50 s
[S1] mode=open target=90 trial=3 achieved=21.3 error=-68.7 deg t=2.0 s wz=0.6 duration=1.50 s
[S1] mode=open target=180 trial=1 achieved=44.6 error=-135.4 deg t=3.6 s wz=0.6 duration=3.00 s
[S1] mode=open target=180 trial=2 achieved=42.7 error=-137.3 deg t=3.6 s wz=0.6 duration=3.00 s
[S1] mode=open target=180 trial=3 achieved=44.6 error=-135.4 deg t=3.6 s wz=0.6 duration=3.00 s
```
```
[S1] mode=move vx=0.8 duration=3.0 s distance=2.24 m heading_change=+3.1 deg t=3.5 s
```

## S2 — Task 3 (Video_Task3 script a–g, typed into main.py)

Pass: ✅ · turn errors [2.0, 1.5, -1.6] · fall ✅ · contacts none · max tilt 7.4° · clip `20261004-0101_baseline/S2_video_task3.mp4`

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
| 01 | `go to the red chair` | ✅ | ✅ | 33/33 (target 23) | SUCCESS | 15.4 | 0.72 | 0.85 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0101_baseline/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 47/54 (target 31) | SUCCESS | 28.1 | 0.77 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0101_baseline/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 58/58 (target 26) | SUCCESS | 13.7 | 0.72 | 0.94 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0101_baseline/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 62/62 (target 31) | SUCCESS | 19.8 | 0.73 | 0.84 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0101_baseline/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/22 (target 0) | FAIL:target_not_found | 10.8 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0101_baseline/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 10.9 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0101_baseline/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 37/39 (target 22) | SUCCESS | 16.2 | 0.75 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0101_baseline/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 26/26 (target 24) | SUCCESS | 18.6 | 0.69 | 0.87 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0101_baseline/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 11.0 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0101_baseline/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 35/35 (target 0) | FAIL:target_not_found | 11.1 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-0101_baseline/S3_10.mp4` |

**S3 success: 3/10**

## S4 — Bonus

Look (clip `20261004-0101_baseline/S4_look.mp4`): VLM answers (correctness checked by hand against the frames):

- **what can you see? (after turn around)** → I see a checkered floor with blue and dark blue squares, a large red square sign on a gray pole in front, a green sign to the left, a yellow sign to the right, and part of a red chair on the far left. The background is a solid blue gradient. (`/home/jiamo/EE4705/EE4705-mini_project/eval/results/vlm/20261004-010936-101270.png`)
- **is there a chair in front of you? (after turn right 45)** → Yes, there is a green chair in front of you, positioned toward the center-right of the view. (`/home/jiamo/EE4705/EE4705-mini_project/eval/results/vlm/20261004-010945-047287.png`)
- **what colour is the ball ahead? (after turn left 90)** → There is no ball visible ahead in the image. The objects present are a red chair and a green square on a stick. (`/home/jiamo/EE4705/EE4705-mini_project/eval/results/vlm/20261004-010952-986951.png`)

Multi-goal (clip `20261004-0101_baseline/S4_multigoal.mp4`): `[MULTI] status=SUCCESS reached=2/2 t=45.6 s` · true d at stops [0.88, 0.67] · strict C2 ❌

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
