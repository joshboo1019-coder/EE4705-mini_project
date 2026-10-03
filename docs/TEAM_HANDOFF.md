# Team handoff — overnight findings (2026-10-04)

Written by Student B after an unattended overnight run (00:30–10:30 SGT). Every item below is an
**issue for its owner, with evidence and a proposed change on its own branch**; nothing in another student's area was
merged into `main`. Branches are on GitHub; `b/overnight-all` is the integration branch that merges the ones that
passed their checks (see MORNING_BRIEF.md).

**About "the handout".** The only PDF on this machine (`~/EE4705/project1.3/EE4705_Project1.3 S1 AY2627.pdf`) is
"Project 1.3: Vision-Language-Action-Based Humanoid" — a different task split (VLM grounding / planner /
manipulation, 20 end-to-end trials, 3–5 min uncut demo) from this repo's MiniLab 1.3 (A: skills, B: LLM parser,
C: YOLO search). Clauses below are therefore quoted from the repo's own guides (`docs/STUDENT_*_README.md`), which
summarise the MiniLab handout. **Please check each clause against the official MiniLab handout.**

How to read the clip names: `~/Videos/e2e/<run>/<suite>_<scenario>.mp4` (not in the repo); per-run tables are in
`eval/e2e/results/<run>/summary.md`.

---

## Everyone (ALL)

### 1. Task 4 must run through `main.py`, with the LLM `[CMD]` line — re-record Video_Task4
- **Clause.** The reference flow is typed English → `[CMD]` → execution ("walk-forward-then-turn, then
  go-to-the-green-chair", docs/STUDENT_README.md, Integration order step 3); C's checklist expects
  `[CMD]` / `[SEARCH]` / `[DETECT]` / `[FOUND]` / `[MISSION]` lines (docs/STUDENT_C_README.md).
- **Issue.** Task 4 trials were run with `perception/task4_cli.py`, which uses a regex parser, not the LLM; its
  `[CMD] input=… action=goto_object(…)` line comes from navigation, and there is no `[CMD] actions=… n=…` from the
  Task 3 parser.
- **Evidence.** `main.py --scenario N` (assist/task4-via-main) runs all 10 of C's layouts through
  `parse_command → executor → goto_object`: 10/10 trials with the LLM `[CMD]` line
  (`eval/e2e/results/20261004-0111_p2a_task4_via_main`). Video_Task4 candidates recorded that way:
  `~/Videos/candidates/Video_Task4_candidate_a.mp4` (blue chair, starts hidden → `[SEARCH]` → `[FOUND] d=0.70 m`),
  `_b.mp4` (green chair among red/blue → `d=0.68 m`), `_c.mp4` (orange ball, paraphrase, hidden start → `d=0.60 m`).
- **Branch.** `assist/task4-via-main` (merged in `b/overnight-all`). **Time:** review 15 min + re-record 20 min.

### 2. Failing tests and CLI flags
- **Issue.** On main, 6 tests fail: `test_handoff` still expects mocks by default, 5 navigation tests are stale.
- **Fix.** `chore/cli-tests`: `main.py --mock` (default stays real), `test_handoff` uses fakes (no sim boot, the
  suite takes 1.6 s instead of 7.6 s), 4 navigation tests updated to the tuned constants, 1 xfail
  (`test_recenter_time_counts_toward_four_second_recovery`: its fake never moves forward — C to say what it meant).
  Integration branch: **114 passed, 1 xfailed**. **Time:** 15 min review.

### 3. Colour-grounding fix — already on main
- PR #4 (`fix/task4-color-grounding`) was merged into main at 00:32 by the repo owner, together with PR #3
  (`bonus_b`). B had planned to hold it until the morning. Evidence for keeping it:
  `docs/task4_color_grounding.md` (offline test set). All of tonight's runs use it. **Decision:** keep (recommended)
  or revert PR #4. **Time:** none if kept.

### 4. Task 1 — compare ≥ 3 LLM-to-robot approaches
- **Clause.** "All three students also share Task 1 (comparing LLM-to-robot approaches, in the report)"
  (docs/STUDENT_README.md).
- **Proposal.** Three approaches with evidence we already have: (1) LLM → JSON action list → validator → skills
  (ours, prompt v1–v5, `eval/task3_eval.md`, `eval/upgrade_eval.md`); (2) structured outputs / function calling
  (the JSON-mode vs json_schema vs function-calling ablation in `eval/upgrade_eval.md`, if it ran); (3) end-to-end
  VLA policies (RT-2 / OpenVLA, cited) and VLM-in-the-loop (our `look` action: `eval/vlm_eval.md`). Plus
  code-as-policies as a 4th (B's `repeat`/`until_see` programs are a restricted, validated form of it).
  **Time:** 1–2 h writing.

### 5. Member table and per-person AI declarations
- The report needs a member table (name, matric no., tasks) and an AI-use declaration per person. B's: Claude
  Code (Anthropic) wrote and ran most of tonight's code/evaluations under B's instructions; every commit carries a
  `Co-Authored-By: Claude` line and the files carry "contributed by Student B (assist)" headers in A's/C's areas.
  **Time:** 20 min.

### 6. Reproducibility and the submission zip
- `chore/repro-zip`: README fixed in 9 places (fresh clone, venv instead of conda for `run_env.sh`, ROS
  `PYTHONPATH`, `.env` keys, YOLO weights, …), `docs/REPRODUCE.md` (fresh clone: 45 s with a warm pip cache, venv
  6.4 GB), `tools/make_submission_zip.sh <commit> --video …` (git-archive based, drops `.env`/`*.pt`/caches/large
  results, scans for keys, prints size; test zip 14 MB / 583 files). Note: the PDF on disk asks for
  `project_1.3_group_<N>.zip`; the script builds `minilab_1.3_group_9.zip` as instructed — **check the official
  name**. `pyproject.toml`'s `[dev]` extra lacks python-dotenv and faster-whisper. **Time:** 15 min.

---

## Student A (Task 2)

### A1. Inconsistent open-loop numbers; turn error measured at loop exit
- **Evidence** (`assist/task2-evidence`, `docs/report_assets/task2/README.md` §3, 108 new trials from logs):
  the bar chart plots the old ~22.5–24.5° open-loop *error* at 90° while the corrected data gives 64–65.6°; no
  script reproduces it; closed-loop errors mix two sources and are taken at loop exit, not settled (+45°: 4.5°
  settled vs 1.52° reported); open-loop rotations were read on a still-moving robot; "1.5 s @ wz 0.6 = 90°" is
  called calibrated but turns ~24° (measured 14.3°/s left, 18.4°/s right); the conclusion ("timing doesn't
  generalise") contradicts the data (a constant 25–28 % fraction means linear scaling works, only the rate is
  wrong); n=24 label over 18 listed trials.
- **New table** (mean |error| ± std, deg, n=6, settled): closed `turn()` +45 4.54±0.16, +90 1.14±0.25,
  +180 2.05±1.59, −45 2.01±1.56, −90 2.91±0.26, −180 2.16±0.82; open-loop with A's mapping 36/69/137° (left);
  open-loop with a calibrated rate 3.1/4.1/9.5° (left). e2e S1 agrees (closed ≤ 1.9° at loop exit, A's open-loop
  ≈ 24 % of target).
- **Also:** `turn(+180)` turned **right** in 6/6 trials (wrap at ±180°) — don't call it a left turn in a video;
  `turn()` exits at |error| ≤ 2° while the robot keeps rotating (settle-and-recheck would fix +45°).
- **Branch.** `assist/task2-evidence` (scripts in `tools/task2_*.py`, nothing in `skills_real.py` changed).
  **Time:** 30 min to adopt the table/figure; 30 min for a settle-and-recheck in `turn()` if wanted.

### A2. Missing YOLO screenshots (2.iii) and onboard-camera evidence (2.ii)
- Now in `docs/report_assets/task2/`: 6 robot-height YOLO detection screenshots, 4 annotated onboard frames, a
  10 s annotated onboard clip (`onboard_clip/task2_onboard_yolo_turn.mp4`, 356 KB). **Time:** 10 min to pick.

---

## Student C (Task 4)

### C1. The C2 stop margin (found ⇒ true distance ≤ 0.80 m)
- **Clause.** "found" only when all of (C1) detected in the live frame at the stop, (C2) planar distance
  ≤ 0.80 m, (C3) logged via `[FOUND]`; ground truth for logging only (docs/STUDENT_C_README.md).
- **Evidence.** The approach stopped at an *estimated* 0.80 m, but chairs' estimates read 0.16 m short
  (`docs/task4_c2_margin.md`). C's own trial table recounted under true d ≤ 0.80 m:
  **6/10 claimed → 1/10** (the "successes" stopped at 0.87, 0.88, 0.87, 1.05, 0.97 m). e2e S3 (typed through main.py):
  baseline **3/10** strict (chairs at true 0.84–0.96 m).
- **Fix.** `assist/c2-margin` (merged in `b/overnight-all`): per-class `APPROACH_STOP_M_BY_CLASS`
  (chair 0.56, ball 0.78, default 0.57) from the measured error distribution; `FOUND_DISTANCE_M = 0.80` kept as the
  C2 check (which now has hysteresis). S3 **6/10** strict, 0 contacts
  (`eval/e2e/results/20261004-0128_p2b_c2_margin_v2`). A single 0.57 m for all classes was tried first and broke
  the ball (it reads long). **Time:** 20 min review; longer-term fix the class-dependent bias in
  `_estimated_planar_distance`.

### C2. Ground truth in the control path
- `navigation._camera_height_above_ground → _target_center_world_height` reads the target body's live world
  height from the simulator (`data.xpos[body_id][2]`, found via its material colour) and feeds it into
  `_estimated_planar_distance`, i.e. into the stop decision (added in b56d8fc). That is simulator ground truth in
  the control path, which the guides forbid for `OBJECT_POSITIONS` and which a reviewer may treat the same way.
  It exists for the blue chair on the stairs. **Proposal:** nominal per-class heights
  (`_DEFAULT_TARGET_CENTER_HEIGHTS_M` already exists) for floor objects, and estimate elevation from the bbox for the
  stairs case. Not changed tonight (C's design decision). **Time:** 1–2 h + re-run S3.

### C3. Stop-sign model
- YOLO labels the scene's square sign plates "stop sign" in 7/387 rendered views; S3's three sign targets fail
  every run. `assist/stopsign` (octagon + white STOP texture): **228/387**, colour grounding unaffected, but chair
  detection drops in frames with a detected sign (314/412 → 238/413), and end to end S3 got **worse, 5/10 vs 6/10**
  (scenario 1: red chair lost near the signs, re-acquire strafes walked into it; elevated signs need their own range
  calibration — yellow sign "SUCCESS" at true 0.93 m). Evidence: `docs/task4_stopsign.md`,
  `eval/e2e/results/20261004-0138_stopsign_eval`. **Not merged.** Decision: keep old signs (recommended for now), or
  adopt + calibrate signs + try the text-free octagon (142/387 signs, smaller chair loss). **Time:** 1–2 h if adopted.

### C4. No obstacle avoidance; close-range C1 failures
- Scenario 2 (original layout): the straight path from spawn to the ball passes the red stop sign at (−1.3, 0);
  two runs brushed its pole (e2e trace contacts).
- **Close range (C1).** With the closer chair stop (P2b), a chair fills the frame (bbox touching the top edge) and
  YOLO's label becomes unstable: in the S4 multi-goal run the red chair at a *true* 0.63 m (C2 satisfied) was
  labelled `bed` (conf 0.18) in the stop frame → `[TRACK] final label conflict not confirmed by target history` →
  `[MISSION] status=FAIL reason=stop_verification` (`eval/e2e/results/20261004-0206_final/S4_multigoal.log`);
  S3 scenario 4 fails the same way. So the margin trades C2 violations (true 0.84–0.96 m) for occasional C1 misses
  at ~0.6 m. **Proposal:** verify C1 on the last frame where the target was still confidently tracked before the
  final step, or let the tracker's identity (`recover_target`, score ≥ 0.9 seen in these logs) confirm a
  frame-filling target. **Time:** 1 h + re-run S3.

### C5. Tests that need C's intent
- `test_recenter_time_counts_toward_four_second_recovery` (xfail on `chore/cli-tests`), the above-camera
  projection test now uses 1.0 m (the 3 m ray falls inside the near-horizontal band since 0b438c0).
- `perception/scenarios.place_robot` teleports a running sim without pausing it; the Task 2 evidence script hit a
  segfault on a *second* teleport in one process (one teleport per launch, as in `main.py --scenario`, was fine in
  all 50 scenario launches tonight).
