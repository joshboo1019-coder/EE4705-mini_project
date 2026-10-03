# MORNING BRIEF — overnight run 2026-10-04 (Student B)

> **Flag 1 — P0 was already done by a teammate.** At 00:32 the repo owner merged PR #3 (`bonus_b`) **and PR #4
> (`fix/task4-color-grounding`)** into main — the colour fix you wanted to hold until the morning. I did not revert it
> (all tonight's runs use it; evidence in `docs/task4_color_grounding.md`). Tag `b-task3-merged` → aa77186 (bonus_b
> merge, before PR #4). Nothing else was pushed to main.
> **Flag 2 — the handout.** The only PDF on disk is "Project 1.3: VLA-based humanoid", which doesn't match MiniLab
> 1.3's task split; clauses were taken from `docs/STUDENT_*_README.md`. Please check against the real handout.

## Pass / fail

| Item | Result | Where |
|---|---|---|
| P0 merge + checks | ✅ tests = pre-merge (6 known failures), mock OK, real-sim smoke OK (ball d = 0.84 m) | STATUS.md |
| P1 harness + baseline | ✅ S1 ✅, S2 7/7 ✅, **S3 3/10** strict, S4 look 3/3 ✅ + multi-goal 2/2 (red chair at 0.88 m) | `eval/e2e/results/20261004-0101_baseline` |
| P2a Task 4 via `main.py --scenario` | ✅ S3 10/10 trials with the LLM `[CMD]` line | `assist/task4-via-main` |
| P2b C2 stop margin | ✅ per-class stop (chair 0.56 / ball 0.78 / other 0.57); S3 **3/10 → 6/10** (v2), 5/10 (final); C's table recounts 6/10 → **1/10** strict | `assist/c2-margin`, `docs/task4_c2_margin.md` |
| P2c Task 2 evidence | ✅ 108 turn trials, 1 table + 1 figure from logs, 6 YOLO screenshots, 10 s annotated clip, 7 inconsistencies in A's numbers | `assist/task2-evidence` |
| P2d CLI + tests | ✅ `--mock`; integration branch **256 passed, 1 xfail** | `chore/cli-tests` |
| P2e repro + zip | ✅ README fixed (9 issues), fresh clone OK, `tools/make_submission_zip.sh` (14 MB) | `chore/repro-zip` |
| P2f stop-sign model | ⚠️ detection 7/387 → 228/387, but e2e S3 **5/10 vs 6/10** → **not merged** | `assist/stopsign` |
| P2g Video_Task4 candidates | ✅ 3 takes via `main.py --scenario`, true d 0.60–0.70 m | `~/Videos/candidates/` |
| P3 B upgrades | ✅ talk-back, repeat/until_see, distance_m, bounds, e-stop fast path, state/status/undo/return_home, v5; Hard set (71, held out) qwen 86 %, gemini 100 %, nano 70 %; injection: **0** unsafe passed; `if_see` not done | `b/upgrade`, `eval/upgrade_eval.md` |
| P4 integrate + final e2e | ✅ S1 same, S2 7/7, **S3 5/10**, S4 3/3 + 2/2 strict, **S5 7/7**; one v5 regression found by S2 and fixed | `eval/e2e/COMPARISON.md` |
| P5 typed demo | DEMO_STATUS | `~/Videos/Video_Bonus_typed_auto.mp4` |
| P6 docs | ✅ `docs/B_code_walkthrough.md` (+15 viva Q&A), `docs/TEAM_HANDOFF.md`, this brief | `b/overnight-all` |
| Extra: v5 noise fix | ❌ v5.1 trades rejections for typo tolerance → keep v5; branch unmerged | `b/v5-noise`, `eval/noise_fix.md` |
| Stretch: hard scene | S6_STATUS | `assist/hard-scene`, `docs/hard_scene.md` |

## Decisions for you (my recommendation first)

1. **Merge `b/overnight-all` into main?** Recommend yes after a skim: it's main + the 7 branches that passed
   their checks (not stopsign / v5-noise / hard-scene). Tests 256 ✅. Owners must OK their areas: A (tools/docs
   only), C (`navigation.py` stop margin, tests), ALL (`main.py`, README).
2. **C2 margin (C's call):** keep the per-class stop (recommended; strict S3 3→5–6/10, 0 contacts) — it trades
   C2 misses at 0.84–0.96 m for occasional C1 misses at ~0.6 m (frame-filling chair labelled "bed").
3. **Stop signs:** keep the old square plates for now (recommended); the octagon needs a sign-range calibration
   and a chair re-check first.
4. **Ground truth in C's range estimate** (`data.xpos` of the target body feeds the stop decision): C to decide;
   at minimum disclose it in the report.
5. **v5 noise regression** (typos rejected as non-English, qwen 8/8 → 4/8 on the Hard set): accept and disclose
   (recommended), or revisit the code-switching rule with a new held-out set.
6. **Video_Task4:** re-record through `main.py --scenario` — or use the candidates as they are.
7. **Zip name:** `minilab_1.3_group_9.zip` (your spec) vs the PDF's `project_1.3_group_<N>.zip`.

## Branches (compare against main: `https://github.com/joshboo1019-coder/EE4705-mini_project/compare/main...<branch>`)

`b/overnight-all` (integration) · `b/upgrade` · `assist/task4-via-main` · `assist/c2-margin` · `assist/task2-evidence`
· `chore/cli-tests` · `chore/repro-zip` · `docs/b-walkthrough` · not merged: `assist/stopsign`, `b/v5-noise`,
`assist/hard-scene`.

## API spend: SPEND_TOTAL of US$2.00 (cap 1.80) — breakdown in STATUS.md

## Videos (none in the repo)

- e2e clips: `~/Videos/e2e/<run>/<suite>_<scenario>.mp4` — baseline `20261004-0101_baseline`, final
  `20261004-0221_final` (+ P2a/P2b/stopsign/delta runs); every row of `eval/e2e/COMPARISON.md` names its clip.
- **Highlights (≤ 3 min): `~/Videos/e2e/highlights.mp4`.**
- Video_Task4 candidates: `~/Videos/candidates/Video_Task4_candidate_{a,b,c}.mp4` — (a) blue chair hidden at
  start → `[SEARCH]` → `[FOUND] class=chair color=blue … d=0.70 m`; (b) green chair among red/blue →
  `[FOUND] … d=0.68 m`; (c) "please head over to the orange ball" → `[FOUND] … d=0.60 m`.
- Typed bonus demo: `~/Videos/Video_Bonus_typed_auto.mp4` (8 segments, frames + timings next to it).

## Cue sheets (full versions in `eval/video_bonus.md`)

**Typed re-record** (one fresh `eval/run_env.sh main.py --gui` on `b/overnight-all`): 1 `turn around` · `what can
you see?` · `turn right 45 degrees` · `is there a chair in front of you?` — 2 `go to the red chair, then the orange
ball` — 3 `keep turning until you see the green chair, then go to it` — 4 `go back to where you started` · `turn left
90 degrees` · `walk in a square with 1 meter sides` · `go back to where you started` — 5 `turn left 45 degrees` · `no,
the other way` · `undo that` — 6 `what did you just do?` — 7 `walk forward half a meter and back half a meter, three
times` then `stop` while it walks — 8 `gira a la derecha noventa grados` then `turn right 90 degrees`.
**Speech segment:** `v` + ENTER before each: "turn left ninety degrees", "walk forward for three seconds, then turn
back", Mandarin "向前走三秒" (rejected by language ID before any LLM call, then the `Did you mean …?` line).

## Risky / unfinished

- Nothing was pushed to main by me; 3 branches are deliberately unmerged (above).
- e2e numbers are n = 1 per scenario per run; S3 varied 5–6/10 between identical-code runs.
- Known limits: an e-stop can't interrupt a running closed-loop `turn()` chunk (≤ 120°); two utterances typed during
  a long batch run as one batch; `goto_object` has no obstacle avoidance (scenario 2 brushes a sign pole).
- Left on disk (outside the repo, not deleted per your rule): fresh-clone venvs (~13 GB) under the session
  scratchpad, `/tmp/himloco_runtime_ui_*` Chrome profiles created by the platform's panel, `/tmp/minilab_scenario_*`
  scene files.
