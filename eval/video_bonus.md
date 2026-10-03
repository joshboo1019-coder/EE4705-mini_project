# Video_Bonus — recording setup and cue sheet

Prepared 2026-10-03 for the bonus video. **Nothing has been recorded yet**: the recording starts only when
the speaker is at the machine. Segments: (1) speech, (2) look, (3) multi-goal, which is filmed only if Part 3
succeeded on the real sim (see segment 3 below).

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

**Part 3 succeeded on the real sim** (`eval/multigoal_eval.md`): with the two goals that reach SUCCESS on
their own (orange ball, red chair), the mission succeeded 3/3 from a fresh launch, in both orders. The green
chair is not used (0/2 on its own).

| # | Input (fresh launch) | Expected | Dry runs |
|---|---|---|---|
| 3a | say (or type) "go to the red chair, then the orange ball" | `[CMD] actions=goto_object(class=chair, color=red), goto_object(class=sports ball, color=orange) n=2`<br>`[FOUND] class=chair color=red …` `[MISSION] status=SUCCESS`<br>`[GOAL] 1/2 red chair status=REACHED t=… s`<br>`[FOUND] class=sports ball color=orange …` `[MISSION] status=SUCCESS`<br>`[GOAL] 2/2 orange sports ball status=REACHED t=… s`<br>`[MULTI] status=SUCCESS reached=2/2 t=… s` | M1 46.0 s, M2 58.7 s |
| fallback | "go to the orange ball and then the red chair" | same, ball first | M3 39.3 s |

Keep the camera on "Third-person follow" so both stops are visible; leave ~1 min per take. If a take ends
`PARTIAL`, relaunch and redo it — the red chair alone failed 1 of 2 single runs (a stop-check boundary case,
see the findings in `eval/multigoal_eval.md`).

**Optional, only if time allows:** "go to the red chair, then the green chair, then the orange ball" shows a
missed goal being skipped (M4: `[GOAL] 2/3 green chair status=NOT_REACHED`, then the ball is reached,
`[MULTI] status=PARTIAL reached=2/3 missed=green_chair`), but it takes ~2.5 min, most of it the green-chair
search. Say clearly in the video that the miss is expected.
