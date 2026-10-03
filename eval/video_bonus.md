# Video_Bonus — recording setup and cue sheet

Prepared 2026-10-03 for the bonus video. **Nothing has been recorded yet**: the recording starts only when
the speaker is at the machine. Segments: (1) speech, (2) look, (3) multi-goal, which is filmed only if Part 3
succeeded on the real sim (see segment 3 below).

## Update 2026-10-04 (overnight run): typed take recorded automatically + cue sheet for the re-record

An automatic **typed** take of the upgraded bonus features was recorded overnight on a virtual display
(`eval/e2e/demo_bonus.py`; `~/Videos/Video_Bonus_typed_auto.mp4`, segment frames and timings next to it in
`Video_Bonus_typed_auto_segments.json`). Record your own version from **`b/overnight-all`** (or main once it is
merged): it has prompt v5, talk-back, programs, state and the stop fast path. One fresh launch for the whole take
(`eval/run_env.sh main.py --gui`); type each line after the previous `[DONE]` / `[CMD] rejected` (+ the `Robot:`
line that follows). Moves are chosen to stay on clear floor: the terrain track starts at x ≈ 1.3–1.5 m ahead of
the spawn heading, the red stop sign stands at (−1.3, 0) behind it.

| # | Segment | Type exactly | What to expect (dry run 2026-10-04 02:00) |
|---|---|---|---|
| 1 | look ×2 | `turn around` · `what can you see?` · `turn right 45 degrees` · `is there a chair in front of you?` | `Robot:` VLM answers (signs + red chair; "Yes, a green chair … centre-right") |
| 2 | multi-goal | `go to the red chair, then the orange ball` | `[GOAL] 1/2 …`, `[GOAL] 2/2 …`, `[MULTI] status=SUCCESS reached=2/2` (in one dry run the red chair failed `stop_verification` and the mission ended `PARTIAL 1/2` — still a valid "skip and continue" shot, but redo the take if you want SUCCESS) |
| 3 | until_see → goto | `keep turning until you see the green chair, then go to it` | `[PLAN] until I see the green chair, up to 8x (turn left 45°) …`, `[UNTIL] … seen …`, `[FOUND] … d≈0.7 m` |
| 4 | 1 m square, then return home | `go back to where you started` · `turn left 90 degrees` · `walk in a square with 1 meter sides` · `go back to where you started` | `[PLAN]`, 4× `[MOVE] target=1.00 m final_error≈±0.02 m`, `Robot: … ending ~0.2 m from where I began`; return home `[PLAN] return home: turn …, walk …, turn …` |
| 5 | undo / repair | `turn left 45 degrees` · `no, the other way` · `undo that` | repair = `turn(-45 deg)` (back to the start heading); undo → `[PLAN] undo: turn …` |
| 6 | status | `what did you just do?` | `Robot: I just did this: …` (answered from the state store, no motion) |
| 7 | mid-program stop | `walk forward half a meter and back half a meter, three times`, then type `stop` while it walks (after `[REPEAT] iteration=2/3`) | `[ESTOP] latency=0.1 ms` (software latency; the robot is at rest ~0.6 s later), `Robot: Emergency stop: …` |
| 8 | non-English → redirect | `gira a la derecha noventa grados` · then `turn right 90 degrees` | `[CMD] rejected reason=non-English`, `Robot: I only take commands in English. Did you mean "turn right 90 degrees"?` — the suggestion is never executed; you type it |

**Speech segment** (your morning addition): use Segment 1 below (two spoken commands, one multi-step, plus the
Mandarin sentence), pressing `v` + ENTER before each. With v5 the non-English rejection is followed by the
`Robot: … Did you mean …?` suggestion line.

**Display tonight:** there was no external monitor, so the automatic take used a virtual display (Xvfb :99,
1920×1080: demo terminal left, panel right). For your own take, the original DP-1 recipe below still applies when
the monitor is connected.

## Setup (once, before the first take)

1. **Code.** Record from the merged code (main after the `bonus_b` + `fix/task4-color-grounding` merge, or the
   local `merge/bonus-b-and-color-fix` branch until it is pushed). It has the speech, look and multi-goal code
   *and* the fixed colour grounding; `bonus_b` alone still has the pre-`9da795e` grounding.
2. **Screen.** Same layout as Video_Task3: DP-1 (2560×1440 at +745+2160) holds the demo terminal on the left
   and the browser panel (`http://localhost:8765`, camera "Third-person follow") on the right. Keep every
   other window (Claude Code, other browsers) on HDMI-0, out of the recorded area.
3. **Microphone.** Default source is the laptop's analog mic (PipeWire); the STT eval was recorded with the
   same device. Input volume reads 24% now (`wpctl status`); do one test `v` and check the transcript before
   recording. PipeWire lets
   `ffmpeg` and the push-to-talk `arecord` share the mic, so the recording keeps the audio while speaking.
4. **Recorder** (in a separate terminal on HDMI-0; press `q` in it to stop):

   ```bash
   ffmpeg -hide_banner -f x11grab -framerate 30 -video_size 2560x1440 -i :1+745,2160 \
          -f pulse -i default \
          -c:v h264_nvenc -preset p5 -cq 23 -pix_fmt yuv420p -c:a aac -b:a 160k \
          ~/Videos/Video_Bonus_raw.mp4
   ```

   Afterwards, trim and scale to 1080p as for Video_Task3:
   `ffmpeg -ss <start> -to <end> -i Video_Bonus_raw.mp4 -vf scale=1920:1080 -c:v libx264 -crf 20 -c:a aac -movflags +faststart Video_Bonus.mp4`.
5. **Launch** (fresh for every segment, so the robot spawns at the origin facing +x):

   ```bash
   eval/run_env.sh main.py --gui
   ```

   Wait for `Type an English command and press ENTER`. The first `v` loads faster-whisper
   (`[STT] loaded faster-whisper small on cuda …`, a few seconds), so do one throw-away `v` + silence
   before starting the recorder, or keep that load in the cut.

**Speaking.** Type `v` + ENTER, then speak at once; recording stops 1 s after you stop talking (5 s max).
The first 0.5 s after ENTER is skipped (the mic "pops"), so start right after that, not before ENTER.
Each spoken command prints `[STT] text="…" lang=… p=… t=… s` and then the same `[CMD]` / `[EXEC]` / `[DONE]`
lines as typed input. Wait for `[DONE]` (or `[CMD] rejected`) before the next `v`.

**Stop the recorder before Ctrl+C** in the demo terminal: Ctrl+C prints a `KeyboardInterrupt` traceback plus
EGL clean-up errors from the render thread.

## Segment 1 — speech (fresh launch)

Same flat-strip order as Video_Task3 (turn left first, so the walk stays on the clear strip at x ≈ 0).

| # | Say (after `v` + ENTER) | Expected lines | Why this one |
|---|---|---|---|
| 1a | "turn left ninety degrees" | `[STT] text="Turn left 90 degrees" lang=en …`<br>`[CMD] actions=turn(90 deg) n=1`<br>`[TURN] target=90.0 deg final_error=…`<br>`[DONE] actions=1` | single-step |
| 1b | "walk forward for three seconds, then turn back" | `[STT] text="Walk forward for 3 seconds, then turn back." lang=en …`<br>`[CMD] actions=move(vx=0.8, 3.0 s), turn(180 deg) n=2`<br>`[EXEC] action=1/2 move …`, `[EXEC] action=2/2 turn …`<br>`[DONE] actions=2` | multi-step; the handout's reference command; 0% WER in the STT eval (M1) |
| 1c | **non-English**, Mandarin: "向前走三秒" (*xiàng qián zǒu sān miǎo*, "walk forward three seconds") | `[MIC] listening …`, `[STT] text="向前走三秒" lang=zh p=1.00 …`<br>`[CMD] rejected reason=non-English` — **before any LLM call**; no `[EXEC]`, the robot stays put | rejected by whisper's language ID (p = 1.00 in the STT eval) |

**Non-English fallback.** If you'd rather say French ("avancez tout droit"): in the STT eval whisper
identified it as English (p = 0.55) and transcribed "Avian's Toad droid", which the LLM then rejected as
non-English. It worked, but by a weaker path; Mandarin (or any language whisper identifies with p ≥ 0.5) is
the cleaner demo.

**If a transcript comes out wrong**, it's still a valid take as long as the parser does the right thing (e.g.
`Side step to a left` still parsed as a left sidestep); otherwise relaunch and redo the segment.

## Segment 2 — look (fresh launch)

These are the commands from the real-sim VLM check (`eval/results/vlm/real_sim_check.log`), so the framing is
known. The turns can be typed or spoken; the two questions should be spoken (`v`) to tie in segment 1.

| # | Input | Expected | Seen in the 2026-10-02 check |
|---|---|---|---|
| 2a | `turn around` | `[CMD] actions=turn(180 deg) n=1` … `[DONE]` | pose −0.09, 0.01, −176° |
| 2b | say "what can you see?" | `[CMD] actions=look("what can you see?") n=1`<br>`[DETECT] …` (YOLO on the same frame)<br>`[VLM] model=qwen3-vl-flash t=… tokens=…`<br>`Robot: I see a red chair on the left, a large red square sign …` | VLM ✅ (red chair, 3 signs); YOLO only finds the chair — worth pointing out |
| 2c | `turn right 45 degrees` | `[CMD] actions=turn(-45 deg) n=1` … `[DONE]` | pose −0.08, 0.03, 144° |
| 2d | say "is there a chair in front of you?" (yes/no) | `[CMD] actions=look("is there a chair in front of you?") n=1`<br>`Robot: Yes, there is a green chair in front of you, …` | VLM ✅; YOLO scores that green chair 0.14, below its 0.2 threshold |

The VLM answers vary in wording between runs; the content above is what to expect.

## Segment 3 — multi-goal

**Part 3 succeeded on the real sim** (`eval/multigoal_eval.md`). On current main (with C's `0b438c0` range fix)
all three goals pass on their own, and both missions below succeeded from a fresh launch.

| # | Input (fresh launch) | Expected | Real-sim runs |
|---|---|---|---|
| 3a | say (or type) "go to the red chair, then the orange ball" | `[CMD] actions=goto_object(class=chair, color=red), goto_object(class=sports ball, color=orange) n=2`<br>`[FOUND] class=chair color=red …` `[MISSION] status=SUCCESS`<br>`[GOAL] 1/2 red chair status=REACHED t=… s`<br>`[FOUND] class=sports ball color=orange …` `[MISSION] status=SUCCESS`<br>`[GOAL] 2/2 orange sports ball status=REACHED t=… s`<br>`[MULTI] status=SUCCESS reached=2/2 t=… s` | 4/4 (39–59 s) |
| 3b (optional) | "go to the red chair, then the green chair, then the orange ball" | the same, with three `[GOAL]` lines and `[MULTI] status=SUCCESS reached=3/3` | 1/1 (110 s; the green-chair search is ~75 s of it) |

3a is the safe take. 3b shows more, but has a single run behind it. If it ends `PARTIAL … missed=green_chair`,
that still shows the skip-and-continue behaviour (as in run M4), so it's usable if you say so on camera.
Keep the camera on "Third-person follow" so each stop is visible. If a take fails, relaunch and redo it.
