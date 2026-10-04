<!-- [B] S3 n = 5 on tag final (1b95477): fixfinal_s3_r1..r3 (fix/final == tag final code) + tag_s3_r4..r5 (worktree of tag final). -->
# S3 strict success on tag `final`, n = 5 per scenario

Runs: `eval/e2e/results/20261004-{1357,1404,1410}_fixfinal_s3_r{1,2,3}` (fix/final head = tag `final` code) and
`docs/report_assets/final/e2e_runs/20261004-{1438,1445}_tag_s3_r{4,5}` (headless `--no-video` on a worktree of tag `final`;
only `summary.md` + `results.jsonl` kept, raw traces not committed). Strict = `[MISSION] status=SUCCESS` + logged
true d ≤ 0.80 m + C1; scenario 10 = correct not-found. Per run: 5, 5, 6, 7, 5 of 10.

**Pooled: 28/50 = 56 %, Wilson 95 % CI [0.42, 0.69].** Per-scenario Wilson CIs: `docs/report_assets/final/s3_success_ci.csv`.
Stop-sign scenarios (05, 06, 09) 0/15 — known limitation (YOLO does not detect the coloured stop signs; `assist/stopsign`
was not merged). Red chair (01, 04) 4/10: all 6 failures happen at the stop with the robot already at true d 0.58–0.65 m
(4 `stop_verification`, 2 `target_not_found` after the F1 re-verify) — YOLO labels the frame-filling red chair "bed"
(C1 not confirmed). Every SUCCESS stopped within 0.80 m (max 0.72 m).

S2 (Task 3 dialogue) ×3 on tag `final`: `docs/report_assets/final/e2e_runs/20261004-145{2,3,4}_tag_s2_r{1,2,3}` — 3/3 pass
(|turn error| ≤ 2.0°, no fall).

| # | Target | final tag, n5 (n=5) |
|---|---|---|
| 01 | red chair | 2/5 (true d 0.58, 0.64, 0.62, 0.68, 0.65; contact runs target 2, other 0) |
| 02 | orange sports ball | 4/5 (true d 0.64, 0.67, 0.62, 0.64, 0.69; contact runs target 0, other 5) |
| 03 | green chair | 5/5 (true d 0.67, 0.69, 0.68, 0.69, 0.72; contact runs target 0, other 0) |
| 04 | red chair | 2/5 (true d 0.63, 0.64, 0.61, 0.66, 0.61; contact runs target 1, other 0) |
| 05 | yellow stop sign | 0/5 (true d 3.78, 3.77, 3.78, 3.79, 3.78; contact runs target 0, other 0) |
| 06 | green stop sign | 0/5 (true d 5.05, 5.04, 5.05, 5.05, 5.03; contact runs target 0, other 0) |
| 07 | orange sports ball | 5/5 (true d 0.66, 0.62, 0.65, 0.64, 0.59; contact runs target 0, other 0) |
| 08 | blue chair | 5/5 (true d 0.63, 0.67, 0.65, 0.65, 0.68; contact runs target 0, other 0) |
| 09 | red stop sign | 0/5 (true d 1.27, 1.26, 1.27, 1.27, 1.27; contact runs target 0, other 0) |
| 10 | blue chair | 5/5 (true d None, None, None, None, None; contact runs target 0, other 0) |
| | **all** | **28/50** (56 %) |

| Class | final tag, n5 |
|---|---|
| chair | strict 14/20; SUCCESS 14 (true d mean/max 0.66/0.72, 0 > 0.80 m); stop_verification 4; contact 3 |
| sports ball | strict 9/10; SUCCESS 9 (true d mean/max 0.64/0.67, 0 > 0.80 m); stop_verification 1; contact 5 |
| stop sign | strict 0/15; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 |
