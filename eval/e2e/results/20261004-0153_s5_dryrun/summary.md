# e2e run `20261004-0153_s5_dryrun`

Commit: `14fe411` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0153_s5_dryrun/` (recorded).

## S5 — B upgrades (typed into main.py)

| Scenario | Checks | Pass | Fall / contacts | Clip |
|---|---|---|---|---|
| until_see | until_line ✅, found_ball ✅, mission_success ✅, summary ✅ | ✅ | ✅ fall, 0 contacts | `20261004-0153_s5_dryrun/S5_until_see.mp4` |
| square | plan ✅, four_sides ✅, closed_back_within_0.5m ✅, summary ✅ | ✅ | ✅ fall, 9 contacts | `20261004-0153_s5_dryrun/S5_square.mp4` |
| return_home | plan ✅, home_within_0.3m ✅, status_answer ✅ | ✅ | ✅ fall, 0 contacts | `20261004-0153_s5_dryrun/S5_return_home.mp4` |
| status | answer_mentions_turn ✅ | ✅ | ✅ fall, 0 contacts | `20261004-0153_s5_dryrun/S5_status.mp4` |
| estop | estop_line ✅, no_llm_for_stop ✅, latency 0.0 ms | ✅ | ✅ fall, 2 contacts | `20261004-0153_s5_dryrun/S5_estop.mp4` |
| non_english | rejected_non_english ✅, suggestion ✅, redirect_turned ✅ | ✅ | ✅ fall, 0 contacts | `20261004-0153_s5_dryrun/S5_non_english.mp4` |
| out_of_range | rejected_out_of_range ✅, suggestion ✅, why_answer ✅ | ✅ | ✅ fall, 0 contacts | `20261004-0153_s5_dryrun/S5_out_of_range.mp4` |

### until_see

```
### >>> typed: keep turning until you see the orange ball, then go to it
[CMD] actions=until_see(class=sports ball, color=orange, max_iter=8: turn(45 deg)), goto_object(class=sports ball, color=orange) n=2
[PLAN] until I see the orange sports ball, up to 8x (turn left 45°), then go to the orange sports ball
[UNTIL] iteration=1/8 target not seen yet
[UNTIL] iteration=2/8 target not seen yet
[UNTIL] iteration=3/8 target not seen yet
[UNTIL] iteration=4/8 target not seen yet
[UNTIL] seen class=sports ball color=orange conf=0.30 after 4 iteration(s)
[CMD] action=goto_object(class=sports ball, color=orange)
[FOUND] class=sports ball color=orange t=25.1 s d=0.50 m
[MISSION] status=SUCCESS
[DONE] actions=2 t=32.3 s
Robot: Done: saw the orange sports ball after 4 tries; reached the orange sports ball; moved 3.0 m, net turn 177° left.
### >>> typed: what have you seen?
[CMD] actions=status(seen) n=1
Robot: I've seen 7 objects: the blue chair (first), last seen 32 s ago at heading +42°; the unknown bench, last seen 31 s ago at heading +87°; the green chair, last seen 28 s ago at heading +175°; the orange sports ball, last seen 3 s ago at heading +176°; the unknown sports ball, last seen 17 s ago at heading +175°; the red airplane, last seen 16 s ago at heading +174°; the orange mouse, last seen 8 s ago at heading +171°.
[DONE] actions=1 t=0.0 s
```

### square

```
### >>> typed: walk in a square with 1 meter sides
[CMD] actions=move(vx=0.8, 1.0 m), turn(90 deg), move(vx=0.8, 1.0 m), turn(90 deg), move(vx=0.8, 1.0 m), turn(90 deg), move(vx=0.8, 1.0 m), turn(90 deg) n=8
[PLAN] walk forward 1 m at 0.8, then turn left 90°, then walk forward 1 m at 0.8, then turn left 90°, then walk forward 1 m at 0.8, then turn left 90°, then walk forward 1 m at 0.8, then turn left 90°
[MOVE] target=1.00 m final_error=0.03 m
[MOVE] target=1.00 m final_error=0.04 m
[MOVE] target=1.00 m final_error=-0.03 m
[MOVE] target=1.00 m final_error=-0.01 m
[DONE] actions=8 t=15.7 s
Robot: Done: walked about 4.4 m, ending 0.0 m from where I began.
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
[PLAN] return home: turn right 178.2°, then walk forward 1.55 m at 0.8, then turn left 86.5°
[MOVE] target=1.55 m final_error=0.00 m
[DONE] actions=1 t=8.2 s
Robot: Done: moved 1.8 m, net turn 93° right.
### >>> typed: how far are you from the start?
[CMD] actions=status(home) n=1
Robot: I'm 0.3 m from where I started (0.1 m ahead, 0.2 m to the right), facing 5° right of my starting direction.
[DONE] actions=1 t=0.0 s
```

### status

```
### >>> typed: turn left 90 degrees
[CMD] actions=turn(90 deg) n=1
[DONE] actions=1 t=2.4 s
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
[MOVE] target=1.00 m final_error=-0.02 m
[ESTOP] latency=0.0 ms
[DONE] actions=0 t=2.0 s
Robot: Emergency stop: I halted during step 1 of 1; walked about 1.1 m, ending 0.8 m from where I began.
### >>> typed: what did you just do?
[CMD] actions=status(last_action) n=1
Robot: I just did this: walk forward 1 metre, then walk backward 1 metre, 3 times (stopped early). Overall I moved 0.8 m.
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
Robot: Done: net turn 88° left.
```

### out_of_range

```
### >>> typed: walk forward for a hundred meters
[CMD] rejected reason=out_of_range:distance
Robot: The longest single move is 30 s, about 24 m at walking speed; I could walk forward for 30 meters instead.
### >>> typed: why did you reject that?
[CMD] actions=status(last_reject) n=1
Robot: I rejected "walk forward for a hundred meters" because the longest single move is 30 s, about 24 m at walking speed. I suggested "walk forward for 30 meters" instead.
[DONE] actions=1 t=0.0 s
```

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
