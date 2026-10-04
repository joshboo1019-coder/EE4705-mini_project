# e2e run `20261004-1416_fixfinal_s2s4s5`

Commit: `711737c` on `fix/final`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1416_fixfinal_s2s4s5/` (recorded).

## S2 — Task 3 (Video_Task3 script a–g, typed into main.py)

Pass: ✅ · turn errors [1.7, 1.6, 1.7, 1.9, 1.8, 1.9, 1.8, 1.6, -1.8, -1.1, -1.8] · fall ✅ · contacts none · max tilt 7.1° · clip –

| Step | Typed | [CMD] line | OK |
|---|---|---|---|
| a | `turn left 90 degrees` | `[CMD] actions=turn(90 deg) n=1` | ✅ |
| b | `walk forward for three seconds, then turn back` | `[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2` | ✅ |
| c | `walk forward for two seconds, then turn right 90 degrees` | `[CMD] actions=move(vx=0.8, 2.0 s), turn(-90 deg) n=2` | ✅ |
| d | `sidestep to your left for two seconds` | `[CMD] actions=move(vx=0, vy=0.8, 2.0 s) n=1` | ✅ |
| e | `do that again, but slower` | `[CMD] actions=move(vx=0, vy=0.3, 2.0 s) n=1` | ✅ |
| f | `fly to the roof` | `[CMD] rejected reason=impossible:fly` | ✅ |
| g | `avancez tout droit` | `[CMD] rejected reason=non-English` | ✅ |

## S4 — Bonus

Look (clip –): VLM answers (correctness checked by hand against the frames):

- **what can you see? (after turn around)** → I see a checkered blue-and-dark-blue floor with reflections. In front is a tall red rectangular sign on a gray pole, with a small yellow sphere near its base. To the left is a green sign on a pole; to the right, a yellow sign on a pole and part of a green chair-like structure. The background is a solid blue gradient. (`/home/jiamo/EE4705/EE4705-mini_project/.worktrees/final/eval/results/vlm/20261004-141704-141263.png`)
- **is there a chair in front of you? (after turn right 45)** → Yes, there is a green chair in front of you, positioned slightly to the right. (`/home/jiamo/EE4705/EE4705-mini_project/.worktrees/final/eval/results/vlm/20261004-141712-689451.png`)
- **what colour is the ball ahead? (after turn left 90)** → The ball ahead is yellow. (`/home/jiamo/EE4705/EE4705-mini_project/.worktrees/final/eval/results/vlm/20261004-141721-298793.png`)

Multi-goal (clip –): `[MULTI] status=PARTIAL reached=1/2 missed=red_chair t=71.5 s` · true d at stops [0.6] · strict C2 ✅

## S5 — B upgrades (typed into main.py)

| Scenario | Checks | Pass | Fall / contacts | Clip |
|---|---|---|---|---|
| until_see | until_line ✅, found_ball ✅, mission_success ✅, summary ✅ | ✅ | ✅ fall, 0 contacts | – |
| square | plan ✅, four_sides ✅, closed_back_within_0.5m ✅, summary ✅ | ✅ | ✅ fall, 4 contacts | – |
| return_home | plan ✅, home_within_0.3m ✅, status_answer ✅ | ✅ | ✅ fall, 0 contacts | – |
| status | answer_mentions_turn ✅ | ✅ | ✅ fall, 0 contacts | – |
| estop | estop_line ✅, no_llm_for_stop ✅, latency 0.0 ms | ✅ | ✅ fall, 1 contacts | – |
| non_english | rejected_non_english ✅, suggestion ✅, redirect_turned ✅ | ✅ | ✅ fall, 0 contacts | – |
| out_of_range | rejected_out_of_range ✅, suggestion ✅, why_answer ✅ | ✅ | ✅ fall, 0 contacts | – |
| spin | chunked_turns ✅, rotated_~720 ✅, rotated 715.4° | ✅ | ✅ fall, 0 contacts | – |

### until_see

```
### >>> typed: keep turning until you see the orange ball, then go to it
[CMD] actions=until_see(class=sports ball, color=orange, max_iter=8: turn(45 deg)), goto_object(class=sports ball, color=orange) n=2
[PLAN] until I see the orange sports ball, up to 8x (turn left 45°), then go to the orange sports ball
[UNTIL] iteration=1/8 target not seen yet
[UNTIL] iteration=2/8 target not seen yet
[UNTIL] iteration=3/8 target not seen yet
[UNTIL] iteration=4/8 target not seen yet
[UNTIL] seen class=sports ball color=orange conf=0.29 after 4 iteration(s)
[CMD] action=goto_object(class=sports ball, color=orange)
[FOUND] class=sports ball color=orange t=17.0 s d=0.58 m
[MISSION] status=SUCCESS
[DONE] actions=2 t=24.3 s
Robot: Done: saw the orange sports ball after 4 tries; reached the orange sports ball; moved 2.9 m, net turn 169° left.
### >>> typed: what have you seen?
[CMD] actions=status(seen) n=1
Robot: I've seen 7 objects: the blue chair (first), last seen 24 s ago at heading +43°; the green chair, last seen 21 s ago at heading +131°; the orange sports ball, last seen 3 s ago at heading +169°; the red stop sign, last seen 18 s ago at heading +176°; the red chair, last seen 16 s ago at heading +177°; the green traffic light, last seen 12 s ago at heading +176°; the orange mouse, last seen 3 s ago at heading +169°; plus 3 other detections without a clear colour (umbrella, bench, sports ball).
[DONE] actions=1 t=0.0 s
```

### square

```
### >>> typed: turn left 90 degrees
[CMD] actions=turn(90 deg) n=1
[DONE] actions=1 t=2.8 s
Robot: Done: net turn 88° left.
### >>> typed: walk in a square with 1 meter sides
[CMD] actions=move(vx=0.8, 1.0 m), turn(90 deg), move(vx=0.8, 1.0 m), turn(90 deg), move(vx=0.8, 1.0 m), turn(90 deg), move(vx=0.8, 1.0 m) n=7
[PLAN] walk forward 1 m at 0.8, then turn left 90°, then walk forward 1 m at 0.8, then turn left 90°, then walk forward 1 m at 0.8, then turn left 90°, then walk forward 1 m at 0.8
[MOVE] target=1.00 m final_error=-0.01 m
[MOVE] target=1.00 m final_error=-0.01 m
[MOVE] target=1.00 m final_error=-0.03 m
[MOVE] target=1.00 m final_error=-0.01 m
[DONE] actions=7 t=15.5 s
Robot: Done: walked about 4.3 m, ending 0.3 m from where I began, net turn 114° right.
```

### return_home

```
### >>> typed: turn left 90 degrees, then walk forward for two seconds
[CMD] actions=turn(90 deg), move(vx=0.8, 2.0 s) n=2
[PLAN] turn left 90°, then walk forward 2 s at 0.8
[DONE] actions=2 t=4.9 s
Robot: Done: moved 1.4 m, net turn 91° left.
### >>> typed: go back to where you started
[CMD] actions=return_home n=1
[PLAN] return home: turn right 178°, then walk forward 1.58 m at 0.8, then turn left 86°
[MOVE] target=1.58 m final_error=-0.01 m
[DONE] actions=1 t=9.0 s
Robot: Done: moved 1.8 m, net turn 93° right.
### >>> typed: how far are you from the start?
[CMD] actions=status(home) n=1
Robot: I'm 0.2 m from where I started (0.1 m ahead, 0.2 m to the right), facing 3° right of my starting direction.
[DONE] actions=1 t=0.0 s
```

### status

```
### >>> typed: turn left 90 degrees
[CMD] actions=turn(90 deg) n=1
[DONE] actions=1 t=2.8 s
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
Robot: Emergency stop: I halted during step 1 of 1; walked about 1.2 m, ending 0.8 m from where I began.
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
[DONE] actions=1 t=2.8 s
Robot: Done: net turn 89° left.
```

### out_of_range

```
### >>> typed: walk forward for a hundred meters
[CMD] rejected reason=out_of_range:distance
Robot: The longest single move is 30 s, about 24 m at walking speed; I could walk forward for 24 meters instead.
### >>> typed: why did you reject that?
[CMD] actions=chat n=1
Robot: I rejected the request because walking 100 meters is beyond my maximum distance limit of 24 meters per motion command.
[DONE] actions=1 t=0.0 s
```

### spin

```
### >>> typed: spin around twice
[CMD] actions=repeat(2x: turn(360 deg)) n=1
[PLAN] repeat 2x (turn left 360°)
[REPEAT] iteration=1/2
[REPEAT] iteration=2/2
[DONE] actions=1 t=19.9 s
Robot: Done: net turn 4° right.
```

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
