<!-- [B] Video checklists. Written by Student B; videos recorded by B on the final tag. -->
# Video cues and checklists (MiniLab 1.3, Group 9)

Requirements are taken from the repo's task guides (the MiniLab 1.3 handout is summarised there:
`docs/STUDENT_A_README.md` §checklist, `docs/STUDENT_B_README.md` §checklist, `docs/STUDENT_C_README.md`
§checklist) plus the group's own list for this round. Every video is recorded from a worktree of tag
`final`, on the primary monitor only (DP-1, 2560×1440 at +745+2160), with only project windows visible.

## Video_Task2 (code: A + B assist; recorded by B) — ~1–3 min
Source: `tools/video_task2_demo.py` on `main.py`'s RealSkills (no LLM).
- [ ] scene + objects visible (panel, third-person view)
- [ ] onboard camera view with the YOLO overlay detecting scene objects (overlay window, `[DETECT]` lines)
- [ ] timed move forward and backward (`[V2]` step lines)
- [ ] lateral moves left and right
- [ ] closed-loop turns left and right incl. 90° and 180°, `[TURN] … final_error=…` visible
- [ ] matching log lines readable in the terminal

## Video_Task3 (code: B) — typed into `eval/run_env.sh main.py --gui`
- [ ] terminal visible throughout; each typed command visible
- [ ] normal command → `[CMD]` → `[EXEC]` → `[DONE]` (autonomous execution)
- [ ] one multi-step command with a turn (`[CMD] actions=move(…), turn(…) n=2`)
- [ ] clarification ("go to the chair" → "Which chair do you mean? …")
- [ ] rejection (`[CMD] rejected reason=impossible:…`)
- [ ] stop (`[ESTOP]` mid-program, robot halts)

## Video_Task4 (code: C + B assist) — scenario 8 + scenario 3 via `main.py --gui --scenario N`
- [ ] terminal visible throughout; typed command visible
- [ ] `[CMD]` / `[SEARCH]` / `[DETECT]` / `[FOUND]` / `[MISSION]` lines
- [ ] ≥ 2 objects: one not initially visible (scenario 8, blue chair) and one same-class disambiguation (scenario 3,
      green chair among red/blue)
- [ ] no contact with any object (e2e trace) and logged true d ≤ 0.80 m at both stops

## Video_Bonus (code: B)
(a) typed, automatic (`eval/e2e/demo_bonus.py --segments look multigoal`):
- [ ] VLM visual QA: `look` questions answered (`[VLM] …`, `Robot: …`)
- [ ] VLM vs YOLO on the same frame: the `[DETECT]` lines (YOLO boxes) printed for the frame the VLM answers about
- [ ] multi-goal mission: `[GOAL] 1/2 … [GOAL] 2/2 … [MULTI] status=SUCCESS`
(b) speech, performed live by B with `tools/record_bonus.sh` (sentences printed by the script):
- [ ] `[STT] text=…` lines visible; two spoken commands (one multi-step) + one non-English sentence rejected
(c) `tools/concat_bonus.sh` joins (a) + (b) into one 1920×1080 H.264/AAC file.

## Recording log
| Video | File | Duration | Size | Checklist | Notes |
|---|---|---|---|---|---|
