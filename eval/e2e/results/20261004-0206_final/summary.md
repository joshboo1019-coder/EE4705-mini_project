# e2e run `20261004-0206_final`

Commit: `22dde7e` on `b/overnight-all`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0206_final/` (recorded).

## S1 — Task 2 skills

| Scenario | Result | Pass | Fall / contacts | Clip |
|---|---|---|---|---|
| closed | max \|error\| 1.9° | ✅ | ✅ fall, 0 contacts | `20261004-0206_final/S1_closed.mp4` |
| open | mean \|error\| 79.8° | ✅ | ✅ fall, 0 contacts | `20261004-0206_final/S1_open.mp4` |
| move | distance 2.28 m | ✅ | ✅ fall, 0 contacts | `20261004-0206_final/S1_move.mp4` |

```
[S1] mode=closed target=45 trial=1 achieved=43.8 error=-1.2 deg t=1.2 s
[S1] mode=closed target=45 trial=2 achieved=43.2 error=-1.8 deg t=1.2 s
[S1] mode=closed target=45 trial=3 achieved=43.1 error=-1.9 deg t=1.2 s
[S1] mode=closed target=90 trial=1 achieved=88.3 error=-1.7 deg t=2.5 s
[S1] mode=closed target=90 trial=2 achieved=88.2 error=-1.8 deg t=2.4 s
[S1] mode=closed target=90 trial=3 achieved=88.8 error=-1.2 deg t=2.5 s
[S1] mode=closed target=180 trial=1 achieved=181.4 error=+1.4 deg t=3.8 s
[S1] mode=closed target=180 trial=2 achieved=181.9 error=+1.9 deg t=3.8 s
[S1] mode=closed target=180 trial=3 achieved=181.2 error=+1.2 deg t=4.0 s
```
```
[S1] mode=open target=45 trial=1 achieved=9.7 error=-35.3 deg t=1.3 s wz=0.6 duration=0.75 s
[S1] mode=open target=45 trial=2 achieved=11.2 error=-33.8 deg t=1.3 s wz=0.6 duration=0.75 s
[S1] mode=open target=45 trial=3 achieved=10.5 error=-34.5 deg t=1.3 s wz=0.6 duration=0.75 s
[S1] mode=open target=90 trial=1 achieved=21.8 error=-68.2 deg t=2.0 s wz=0.6 duration=1.50 s
[S1] mode=open target=90 trial=2 achieved=21.0 error=-69.0 deg t=2.0 s wz=0.6 duration=1.50 s
[S1] mode=open target=90 trial=3 achieved=21.6 error=-68.4 deg t=2.0 s wz=0.6 duration=1.50 s
[S1] mode=open target=180 trial=1 achieved=44.7 error=-135.3 deg t=3.6 s wz=0.6 duration=3.00 s
[S1] mode=open target=180 trial=2 achieved=42.2 error=-137.8 deg t=3.6 s wz=0.6 duration=3.00 s
[S1] mode=open target=180 trial=3 achieved=44.1 error=-135.9 deg t=3.6 s wz=0.6 duration=3.00 s
```
```
[S1] mode=move vx=0.8 duration=3.0 s distance=2.28 m heading_change=+3.2 deg t=3.5 s
```

## S2 — Task 3 (Video_Task3 script a–g, typed into main.py)

Pass: ❌ · turn errors [1.4, -1.1, -1.3, -1.5] · fall ✅ · contacts none · max tilt 6.9° · clip `20261004-0206_final/S2_video_task3.mp4`

| Step | Typed | [CMD] line | OK |
|---|---|---|---|
| a | `turn left 90 degrees` | `[CMD] actions=turn(90 deg) n=1` | ✅ |
| b | `walk forward for three seconds, then turn back` | `[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2` | ✅ |
| c | `walk forward for two seconds, then turn right 90 degrees` | `[CMD] actions=move(vx=0.8, 2.0 s), turn(-90 deg) n=2` | ✅ |
| d | `sidestep to your left for two seconds` | `[CMD] actions=move(vx=0, vy=0.8, 2.0 s) n=1` | ✅ |
| e | `do that again, but slower` | `None` | ❌ |
| f | `fly to the roof` | `[CMD] rejected reason=impossible:fly` | ✅ |
| g | `avancez tout droit` | `[CMD] rejected reason=non-English` | ✅ |

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 37/37 (target 26) | SUCCESS | 34.1 | 0.56 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0206_final/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 65/78 (target 46) | SUCCESS | 32.8 | 0.75 | 0.62 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0206_final/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 62/62 (target 29) | SUCCESS | 15.3 | 0.46 | 0.71 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0206_final/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 61/61 (target 30) | FAIL:stop_verification | 24.5 | None | 0.59 | ❌ | ❌ | ✅ | ❌ | ❌ | `20261004-0206_final/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 13/19 (target 0) | FAIL:target_not_found | 10.8 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0206_final/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/11 (target 0) | FAIL:target_not_found | 10.8 | None | 5.05 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0206_final/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 32/37 (target 21) | SUCCESS | 20.1 | 0.7 | 0.59 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0206_final/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 30/30 (target 27) | SUCCESS | 17.1 | 0.44 | 0.63 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0206_final/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 10.8 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0206_final/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 35/35 (target 0) | FAIL:target_not_found | 10.8 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-0206_final/S3_10.mp4` |

**S3 success: 6/10**

## S4 — Bonus

Look (clip `20261004-0206_final/S4_look.mp4`): VLM answers (correctness checked by hand against the frames):

- **what can you see? (after turn around)** → I see a checkered blue-and-dark-blue floor with several colored objects: a large red square sign on a gray pole in front, a green rectangular sign to the left, a yellow rectangular sign to the right, part of a red chair on the far left, and a partial green object on the far right. The background is a solid dark blue. (`/home/jiamo/EE4705/EE4705-mini_project/eval/results/vlm/20261004-021533-357549.png`)
- **is there a chair in front of you? (after turn right 45)** → Yes, there is a green chair in front of you, positioned toward the center-right of the view. (`/home/jiamo/EE4705/EE4705-mini_project/eval/results/vlm/20261004-021542-140288.png`)
- **what colour is the ball ahead? (after turn left 90)** → The ball ahead is orange. (`/home/jiamo/EE4705/EE4705-mini_project/eval/results/vlm/20261004-021550-332710.png`)

Multi-goal (clip `20261004-0206_final/S4_multigoal.mp4`): `[MULTI] status=PARTIAL reached=1/2 missed=red_chair t=59.0 s` · true d at stops [0.54] · strict C2 ✅

## S5 — B upgrades (typed into main.py)

| Scenario | Checks | Pass | Fall / contacts | Clip |
|---|---|---|---|---|
| until_see | until_line ✅, found_ball ✅, mission_success ✅, summary ✅ | ✅ | ✅ fall, 1 contacts | `20261004-0206_final/S5_until_see.mp4` |
| square | plan ✅, four_sides ✅, closed_back_within_0.5m ✅, summary ✅ | ✅ | ✅ fall, 6 contacts | `20261004-0206_final/S5_square.mp4` |
| return_home | plan ✅, home_within_0.3m ❌, status_answer ✅ | ❌ | ✅ fall, 0 contacts | `20261004-0206_final/S5_return_home.mp4` |
| status | answer_mentions_turn ✅ | ✅ | ✅ fall, 0 contacts | `20261004-0206_final/S5_status.mp4` |
| estop | estop_line ✅, no_llm_for_stop ✅, latency 0.0 ms | ✅ | ✅ fall, 2 contacts | `20261004-0206_final/S5_estop.mp4` |
| non_english | rejected_non_english ✅, suggestion ✅, redirect_turned ✅ | ✅ | ✅ fall, 0 contacts | `20261004-0206_final/S5_non_english.mp4` |
| out_of_range | rejected_out_of_range ✅, suggestion ✅, why_answer ✅ | ✅ | ✅ fall, 0 contacts | `20261004-0206_final/S5_out_of_range.mp4` |

### until_see

```
### >>> typed: keep turning until you see the orange ball, then go to it
[CMD] actions=until_see(class=sports ball, color=orange, max_iter=8: turn(45 deg)), goto_object(class=sports ball, color=orange) n=2
[PLAN] until I see the orange sports ball, up to 8x (turn left 45°), then go to the orange sports ball
[UNTIL] iteration=1/8 target not seen yet
[UNTIL] iteration=2/8 target not seen yet
[UNTIL] iteration=3/8 target not seen yet
[UNTIL] iteration=4/8 target not seen yet
[UNTIL] seen class=sports ball color=orange conf=0.21 after 4 iteration(s)
[CMD] action=goto_object(class=sports ball, color=orange)
[FOUND] class=sports ball color=orange t=17.5 s d=0.59 m
[MISSION] status=SUCCESS
[DONE] actions=2 t=24.6 s
Robot: Done: saw the orange sports ball after 4 tries; reached the orange sports ball; moved 2.9 m, net turn 174° left.
### >>> typed: what have you seen?
[CMD] actions=status(seen) n=1
Robot: I've seen 4 objects: the blue chair (first), last seen 24 s ago at heading +43°; the green chair, last seen 21 s ago at heading +130°; the orange sports ball, last seen 3 s ago at heading +174°; the orange mouse, last seen 3 s ago at heading +174°; plus 2 other detections without a clear colour (bench, sports ball).
[DONE] actions=1 t=0.0 s
```

### square

```
### >>> typed: turn left 90 degrees
[CMD] actions=turn(90 deg) n=1
[DONE] actions=1 t=2.4 s
Robot: Done: net turn 88° left.
### >>> typed: walk in a square with 1 meter sides
[CMD] actions=move(vx=0.8, 1.0 m), turn(90 deg), move(vx=0.8, 1.0 m), turn(90 deg), move(vx=0.8, 1.0 m), turn(90 deg), move(vx=0.8, 1.0 m) n=7
[PLAN] walk forward 1 m at 0.8, then turn left 90°, then walk forward 1 m at 0.8, then turn left 90°, then walk forward 1 m at 0.8, then turn left 90°, then walk forward 1 m at 0.8
[MOVE] target=1.00 m final_error=-0.03 m
[MOVE] target=1.00 m final_error=-0.01 m
[MOVE] target=1.00 m final_error=-0.02 m
[MOVE] target=1.00 m final_error=-0.01 m
[DONE] actions=7 t=14.2 s
Robot: Done: walked about 4.3 m, ending 0.1 m from where I began, net turn 97° right.
```

### return_home

```
### >>> typed: turn left 90 degrees, then walk forward for two seconds
[CMD] actions=turn(90 deg), move(vx=0.8, 2.0 s) n=2
[PLAN] turn left 90°, then walk forward 2 s at 0.8
[DONE] actions=2 t=4.5 s
Robot: Done: moved 1.4 m, net turn 91° left.
### >>> typed: go back to where you started
[CMD] actions=return_home n=1
[PLAN] return home: turn right 178.4°, then walk forward 1.57 m at 0.8, then turn left 86.5°
[MOVE] target=1.57 m final_error=0.00 m
[DONE] actions=1 t=8.4 s
Robot: Done: moved 1.8 m, net turn 93° right.
### >>> typed: how far are you from the start?
[CMD] actions=status(home) n=1
Robot: I'm 0.3 m from where I started (0.2 m ahead, 0.2 m to the right), facing the way I started.
[DONE] actions=1 t=0.0 s
```

### status

```
### >>> typed: turn left 90 degrees
[CMD] actions=turn(90 deg) n=1
[DONE] actions=1 t=2.5 s
Robot: Done: net turn 88° left.
### >>> typed: what did you just do?
[CMD] actions=status(last_action) n=1
Robot: I just did this: turn left 90 degrees. Overall I turned 88° left.
[DONE] actions=1 t=0.0 s
```

### estop

```
### >>> typed: walk forward 1 meter and back 1 meter, three times
[CMD] actions=repeat(3x: move(vx=0.8, 1.0 m), move(vx=-0.8, 1.0 m)) n=1
[PLAN] repeat 3x (walk forward 1 m at 0.8, then walk backward 1 m at 0.8)
[REPEAT] iteration=1/3
### >>> typed: stop
[MOVE] target=1.00 m final_error=0.03 m
[ESTOP] latency=0.0 ms
[DONE] actions=0 t=2.1 s
Robot: Emergency stop: I halted during step 1 of 1; walked about 1.1 m, ending 0.9 m from where I began.
### >>> typed: what did you just do?
[CMD] actions=status(last_action) n=1
Robot: I just did this: walk forward 1 metre, then walk backward 1 metre, 3 times (stopped early). Overall I moved 0.9 m.
[DONE] actions=1 t=0.0 s
```

### non_english

```
### >>> typed: gira a la izquierda noventa grados
[CMD] rejected reason=non-English
Robot: I only take commands in English. Did you mean "turn left 90 degrees"?
### >>> typed: turn left 90 degrees
[CMD] actions=turn(90 deg) n=1
[DONE] actions=1 t=2.5 s
Robot: Done: net turn 89° left.
```

### out_of_range

```
### >>> typed: walk forward for a hundred meters
[CMD] rejected reason=out_of_range:distance_m
Robot: The longest single move is 30 s, about 24 m at walking speed; I could walk forward for 24 meters instead.
### >>> typed: why did you reject that?
[CMD] actions=chat n=1
Robot: I rejected the request because walking 100 meters is beyond my maximum distance limit of 24 meters per motion command.
[DONE] actions=1 t=0.0 s
```

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
