# Bonus Part 3 — multi-goal missions

Branch `bonus_b`, 2026-10-03. A single utterance with two or more `goto_object` actions ("go to the red chair,
then the orange ball") is run as one mission: the goals are visited in order, a goal that isn't reached is
skipped (the robot goes on to the next one), and a summary line closes the batch.

**Headline (current main, `0b438c0` range code + colour fix):** all three goals reach SUCCESS on their own, and
a 3-goal mission red chair → green chair → orange ball succeeded **3/3 in 109.7 s** (run M6). Runs M1–M4 below
were made before `0b438c0` and are kept as recorded.

## What changed

- **Parser: nothing.** Prompt v4 already turns multi-step instructions into an ordered action list. Four
  multi-goal cases were added to the eval after v4 was frozen (none is a prompt example) and run once per
  service: **12/12** (qwen-flash, gemini-3.8-flash, gpt-5-nano each 4/4; logged in `eval/results/v4/`).

  | Case | Utterance | Expected actions |
  |---|---|---|
  | G1 | go to the orange ball, then the green chair | goto(orange ball), goto(green chair) |
  | G2 | visit the red chair, the green chair and then the orange ball | goto(red chair), goto(green chair), goto(orange ball) |
  | G3 | first find the green chair and after that go to the red one | goto(green chair), goto(red chair) |
  | G4 | go to the green chair, then turn around and go to the orange ball | goto(green chair), turn(180), goto(orange ball) |

- **Executor (`dialogue/executor.py`).** `goto_object` already returns True only when `[MISSION] status=SUCCESS`
  was printed. When a batch has ≥ 2 goto actions the executor records each result and prints

  ```
  [GOAL] <k>/<n> <color> <class> status=REACHED|NOT_REACHED t=<s since batch start> s
  [MULTI] status=SUCCESS|PARTIAL|FAIL reached=<r>/<n> [missed=<a>,<b>] [not_attempted=<m>] t=<s> s
  ```

  SUCCESS = every goal reached, PARTIAL = some, FAIL = none. A goal that isn't reached does **not** end the
  batch (C's `goto_object` stops the robot before returning False). An exception still ends the batch as
  before, and the goals after it are counted as `not_attempted`. A batch with one goto prints no `[GOAL]` /
  `[MULTI]` lines, so Task 4 output is unchanged.
- **Tests:** 7 offline tests in `tests/test_bonus_b.py` (navigation faked): all reached, a missed goal is
  skipped and the next one still runs, none reached, goals mixed with a turn, an exception mid-mission, single
  goto unchanged, parser keeps goal order.

## Choosing the goals: single-goal runs from a fresh launch

Rule: a goal is used only if it reaches `[MISSION] status=SUCCESS` on its own from a fresh launch. Code: the
merged tree (main + `bonus_b` + `fix/task4-color-grounding`), so navigation is main's and colour grounding is the
fix branch's. **First round** (this table, M1–M4): main at `9dbd91e`, before Student C's `0b438c0` ("separated
estimated_planar calculation for ground-level and varying-level objects", landed 2026-10-03 afternoon). The
**second round** on main at `d0f7a23` (which includes `0b438c0`) is further down. `eval/run_env.sh main.py --gui`,
commands typed by a driver script. Logs: `eval/results/multigoal/`.

| Goal | Runs | Result | Notes |
|---|---|---|---|
| orange ball | 1 | **1/1** SUCCESS (d = 0.67 m) | the Part 2 merge smoke test |
| red chair | 2 | **1/2** | run 1: `FAIL reason=stop_verification` — approach stopped at estimate ≤ 0.80 m (true 0.92 m), then the post-stop check read 0.80 m > `FOUND_DISTANCE_M` = 0.8; run 2: SUCCESS in 17.9 s, d = 0.90 m |
| green chair | 2 | **0/2** | run 1: `FAIL reason=timeout` (122.9 s); run 2: `FAIL reason=target_not_found` (93.9 s). YOLO sees it (conf 0.8–0.9) and the robot gets within 0.76–0.83 m true distance, but the range estimate is too long (see below), so it never stops |
| stop signs | – | not tried | YOLO labels the scene's square "+" plates "stop sign" in only 7 of 387 rendered views |

**Goals used: orange ball and red chair.** The green chair is left out by the rule; it is still used once below,
to show that a missed goal is skipped.

## Real-sim multi-goal runs (fresh launch each)

| # | Utterance | Goals | `[MULTI]` | Time | `[FOUND]` true distance per goal |
|---|---|---|---|---|---|
| M1 | go to the red chair, then the orange ball | red chair, orange ball | **SUCCESS 2/2** | 46.0 s | 1.15 m, 0.62 m |
| M2 | go to the red chair, then the orange ball | red chair, orange ball | **SUCCESS 2/2** | 58.7 s | 1.19 m, 0.62 m |
| M3 | go to the orange ball and then the red chair | orange ball, red chair | **SUCCESS 2/2** | 39.3 s | 0.62 m, 1.40 m |
| M4 | go to the red chair, then the green chair, then the orange ball | red, green, ball | **PARTIAL 2/3** `missed=green_chair` | 141.5 s | 0.78 m, — (`stop_verification` at 127.4 s), 0.70 m |

So with the two viable goals the mission succeeded 3/3, in both orders; M4 shows the skip on the real sim: the
green chair fails after ~107 s, the robot goes on and reaches the ball 14 s later. M1's terminal lines:

```
[CMD] actions=goto_object(class=chair, color=red), goto_object(class=sports ball, color=orange) n=2
[FOUND] class=chair color=red t=23.6 s d=1.15 m
[MISSION] status=SUCCESS
[GOAL] 1/2 red chair status=REACHED t=23.6 s
[FOUND] class=sports ball color=orange t=22.4 s d=0.62 m
[MISSION] status=SUCCESS
[GOAL] 2/2 orange sports ball status=REACHED t=46.0 s
[MULTI] status=SUCCESS reached=2/2 t=46.0 s
[DONE] actions=2 t=46.0 s
```

(`[FOUND] t=` is per goal, from C's `goto_object`; `[GOAL] t=` is from the start of the batch.)

**Mock run** (`eval/mock_main.py`, "go to the green chair, then the orange ball"): `[GOAL] 1/2 … NOT_REACHED`,
`[GOAL] 2/2 … NOT_REACHED`, `[MULTI] status=FAIL reached=0/2 missed=green_chair,orange_sports_ball`. Both
misses are mock limits, not Part 3 bugs: the mock green-chair bbox never centres (known, `eval/task3_eval.md`),
and the mock perception has no ball. It confirms the mission path end to end. The mock re-centring loop
printed 16 M lines in 180 s; the committed log has them collapsed.

## Second round: current main (`d0f7a23`, includes `0b438c0`)

Merge rebuilt from `origin/main` at `d0f7a23` + `bonus_b` + the fix branch; fresh launch per row.

| # | Input | Result | Notes |
|---|---|---|---|
| S | turn left 90 degrees; go to the orange ball | turn final_error 1.7°; ball SUCCESS, d = 0.66 m, 31.0 s | the Part 2 smoke test (`smoke2.log`) |
| G | go to the green chair | **SUCCESS**, d = 0.95 m, 15.0 s | estimate now 0.23 m *short* on average (was 0.3–1.8 m long) |
| M5 | go to the red chair, then the orange ball | **SUCCESS 2/2**, 39.0 s | red chair d = 0.91 m, ball 0.68 m |
| M6 | go to the red chair, then the green chair, then the orange ball | **SUCCESS 3/3**, 109.7 s | d = 0.88 / 0.93 / 0.66 m; the green-chair search took 76.4 s |

So C's `0b438c0` fixed the green-chair range problem found in the first round; with it, all three candidate
goals pass the single-goal rule (green chair n = 1 so far). Over both rounds the red chair + orange ball
mission is **4/4**.

## Findings for Task 4 (Student C) from the first round

The first two are about the range code *before* `0b438c0`; the second round suggests it fixed them.

- **Green chair range estimate was too long**: `estimated_planar − ground_truth` averaged +1.81 m, +0.62 m and
  +0.30 m over the three green-chair approaches (e.g. 2.27 m estimated at 0.76 m true). The robot is close
  enough but never passes `estimated ≤ 0.8 m`, then loses the chair at close range and strafes.
- **Red chair estimate was short** (−0.1 to −0.4 m), so `[FOUND]` fired at 1.15–1.40 m true distance (0.88–0.91 m
  in the second round).
- **Stop check has no hysteresis** (still true on current main): the approach stops at estimate ≤ 0.8 m, and the post-stop check re-measures
  against the same 0.8 m. Red chair run 1 failed `stop_verification` reading 0.80 m both times (≤ before the
  stop, just over after). A small margin in the stop check (e.g. 0.8 m + 0.05 m) would avoid that.

n is small (1–4 runs per row); these are spot checks, not rates.
