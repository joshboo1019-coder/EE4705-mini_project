<!-- [B] Video checklists. Written by Student B; videos recorded by B on the final tag. -->
# Video cues and checklists (MiniLab 1.3, Group 9)

Requirements are taken from the repo's task guides (the MiniLab 1.3 handout is summarised there:
`docs/STUDENT_A_README.md` §checklist, `docs/STUDENT_B_README.md` §checklist, `docs/STUDENT_C_README.md`
§checklist) plus the group's own list for this round. Every video is recorded from a worktree of tag
`final`, on the primary monitor only (DP-1, 2560×1440 at +745+2160), with only project windows visible.

## Video_Task2 (code: A + B assist; recorded by B) — ~1–3 min
Source: `tools/video_task2_demo.py` on `main.py`'s RealSkills (no LLM).
- [x] scene + objects visible (panel, third-person view)
- [x] onboard camera view with the YOLO overlay detecting scene objects (overlay window, `[DETECT]` lines)
- [x] timed move forward and backward (`[V2]` step lines)
- [x] lateral moves left and right
- [x] closed-loop turns left and right incl. 90° and 180°, `[TURN] … final_error=…` visible
- [x] matching log lines readable in the terminal

## Video_Task3 (code: B) — typed into `eval/run_env.sh main.py --gui`
- [x] terminal visible throughout; each typed command visible
- [x] normal command → `[CMD]` → `[EXEC]` → `[DONE]` (autonomous execution)
- [x] one multi-step command with a turn (`[CMD] actions=move(…), turn(…) n=2`)
- [x] clarification ("go to the chair" → "Which chair do you mean? …")
- [x] rejection (`[CMD] rejected reason=impossible:…`)
- [x] stop (`[ESTOP]` mid-program, robot halts)

## Video_Task4 (code: C + B assist) — scenario 8 + scenario 3 via `main.py --gui --scenario N`
- [x] terminal visible throughout; typed command visible
- [x] `[CMD]` / `[SEARCH]` / `[DETECT]` / `[FOUND]` / `[MISSION]` lines
- [x] ≥ 2 objects: one not initially visible (scenario 8, blue chair) and one same-class disambiguation (scenario 3,
      green chair among red/blue)
- [x] no contact with any object (e2e trace) and logged true d ≤ 0.80 m at both stops

## Video_Bonus (code: B)
(a) typed, automatic (`eval/e2e/demo_bonus.py --segments look multigoal`):
- [x] VLM visual QA: `look` questions answered (`[VLM] …`, `Robot: …`)
- [x] VLM vs YOLO on the same frame: the `[DETECT]` lines (YOLO boxes) printed for the frame the VLM answers about
- [x] multi-goal mission: `[GOAL] 1/2 … [GOAL] 2/2 … [MULTI] status=SUCCESS`
(b) speech, performed live by B with `tools/record_bonus.sh` (sentences printed by the script):
- [ ] `[STT] text=…` lines visible; two spoken commands (one multi-step) + one non-English sentence rejected
(c) `tools/concat_bonus.sh` joins (a) + (b) into one 1920×1080 H.264/AAC file.

## Recording log
| Video | File | Duration | Size | Checklist | Notes |
|---|---|---|---|---|---|
| Video_Task2 | `~/Videos/candidates/Video_Task2_final_tag.mp4` | 45.9 s | 14 MB | all ✓ | DP-1 work area 2494×1408 (+811+2192: monitor minus GNOME top bar/dock); `tools/video_task2_demo.py`; Qt font warnings scroll by in the first seconds; shorter than the 1–3 min guide (choreography is fixed in the tag). First take discarded (top bar + dock visible). |
| Video_Task3 | `~/Videos/candidates/Video_Task3_final_tag.mp4` | 36.3 s | 6.6 MB | all ✓ | DP-1 work area 2494×1408; typed: turn left 90 · walk 3 s then turn back · go to the chair (clarify) · fly to the roof (reject) · program + stop (`[ESTOP]`). Fallback: `~/Videos/Video_Task3.mp4`. |
| Video_Task4 | `~/Videos/candidates/Video_Task4_final_tag.mp4` | 50.3 s | 9.2 MB | all ✓ | scenario 8 (blue chair, `[SEARCH]`, true d 0.60 m) + scenario 3 (green chair, true d 0.68 m), 0 contacts (run `20261004-1429_video_task4_tag`), 1920×1080. Fallback: `Video_Task4_final.mp4`. |
| Video_Bonus (a) | `~/Videos/candidates/Video_Bonus_typed_final_tag.mp4` | 167.6 s | 25 MB | (a) ✓ | look ×2 (VLM + YOLO `[DETECT]` on the same frame) + 2-goal mission `[MULTI] status=SUCCESS reached=2/2` (red chair 0.77 m, ball 0.57 m). Two takes joined: in the single take the mission after the looks was rejected by the LLM ("impossible: object not seen" — v5 STATE limitation), and one fresh-launch mission take was PARTIAL (red chair missed); the kept mission take is a separate fresh launch. |
| Video_Bonus (b)+(c) | dry run `~/Videos/candidates/Video_Bonus_final_dryrun.mp4` | 192.6 s | 27 MB | (b) pending (B speaks live) | `tools/record_bonus.sh --dry-run` (typed stand-ins, mic audio) + `tools/concat_bonus.sh` → 1920×1080 H.264/AAC: scripts proven. |
