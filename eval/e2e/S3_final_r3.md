<!-- [B] S3 on final-r3 code (n = 5) vs final-r2 (n = 5). Written by Student B. -->
# S3 strict success: final-r3 (n = 5) vs final-r2 (n = 5)

final-r3 = final-r2 + iter/close-range-c1 (re-identify the target on a final label conflict) + prompt v5.1
(iter/state-unseen) + fix/hygiene (harness SIGINT stop, --mock without platform, EOF quit, launch-race readiness
wait) + scaled VLM eval (docs). Runs (headless `--no-video`, summary.md + results.jsonl only, no raw traces):
`eval/e2e/results/20261004-{1716,1739,1754}_rc_s3_r{1,2,3}` (branch `rc`, code identical to final-r3) and
`docs/report_assets/final/e2e_runs/20261004-{1815,1823}_r3tag_s3_r{4,5}` (worktree of final-r4 = final-r3 code).

**final-r3: 31/50 = 6.2 per run (5, 7, 6, 6, 7), Wilson 95 % [0.48, 0.74]; final-r2: 28/50 = 5.6 per run [0.42, 0.69].**
Target-contact runs: final-r3 2/50 — r1 sc01 (chair lost close-up, growing re-acquire strafes pushed the robot into it,
true d 0.24 m) and r4 sc04 (touched the red chair, stopped at true 0.86 m, not strict) — both the known re-acquire
limitation fixed on the unmerged `iter/chair-safety`; final-r2 3/50. Other-object contact: sc02 touches the red stop
sign on the way to the ball in 5/5 (final-r2 5/5). Stop signs 0/15 in both.
Not merged (gates failed): `iter/chair-safety` (sc01+sc04 5/6 strict, 0 target contacts, but sc03/sc08 1/2 each),
`iter/avoid` (26/30 strict incl. stop signs, but 2 false [FOUND] on sc06 and target/other contacts).

| # | Target | final-r2, n5 (n=5) | final-r3, n5 (n=5) |
|---|---|---|---|
| 01 | red chair | 2/5 (true d 0.58, 0.64, 0.62, 0.68, 0.65; contact runs target 2, other 0) | 3/5 (true d 0.24, 0.6, 0.66, 0.69, 0.66; contact runs target 1, other 0) |
| 02 | orange sports ball | 4/5 (true d 0.64, 0.67, 0.62, 0.64, 0.69; contact runs target 0, other 5) | 5/5 (true d 0.61, 0.61, 0.63, 0.62, 0.63; contact runs target 0, other 5) |
| 03 | green chair | 5/5 (true d 0.67, 0.69, 0.68, 0.69, 0.72; contact runs target 0, other 0) | 4/5 (true d 0.72, 0.71, 0.68, 0.72, 0.7; contact runs target 0, other 0) |
| 04 | red chair | 2/5 (true d 0.63, 0.64, 0.61, 0.66, 0.61; contact runs target 1, other 0) | 4/5 (true d 0.63, 0.62, 0.59, 0.86, 0.58; contact runs target 1, other 0) |
| 05 | yellow stop sign | 0/5 (true d 3.78, 3.77, 3.78, 3.79, 3.78; contact runs target 0, other 0) | 0/5 (true d 3.78, 3.77, 3.77, 3.78, 3.78; contact runs target 0, other 0) |
| 06 | green stop sign | 0/5 (true d 5.05, 5.04, 5.05, 5.05, 5.03; contact runs target 0, other 0) | 0/5 (true d 5.05, 5.05, 5.06, 5.04, 5.04; contact runs target 0, other 0) |
| 07 | orange sports ball | 5/5 (true d 0.66, 0.62, 0.65, 0.64, 0.59; contact runs target 0, other 0) | 5/5 (true d 0.59, 0.66, 0.66, 0.62, 0.59; contact runs target 0, other 0) |
| 08 | blue chair | 5/5 (true d 0.63, 0.67, 0.65, 0.65, 0.68; contact runs target 0, other 0) | 5/5 (true d 0.62, 0.68, 0.62, 0.64, 0.66; contact runs target 0, other 0) |
| 09 | red stop sign | 0/5 (true d 1.27, 1.26, 1.27, 1.27, 1.27; contact runs target 0, other 0) | 0/5 (true d 1.27, 1.31, 1.27, 1.27, 1.28; contact runs target 0, other 0) |
| 10 | blue chair | 5/5 (true d None, None, None, None, None; contact runs target 0, other 0) | 5/5 (true d None, None, None, None, None; contact runs target 0, other 0) |
| | **all** | **28/50** (56 %) | **31/50** (62 %) |

| Class | final-r2, n5 | final-r3, n5 |
|---|---|---|
| chair | strict 14/20; SUCCESS 14 (true d mean/max 0.66/0.72, 0 > 0.80 m); stop_verification 4; contact 3 | strict 16/20; SUCCESS 17 (true d mean/max 0.66/0.86, 1 > 0.80 m); stop_verification 2; contact 2 |
| sports ball | strict 9/10; SUCCESS 9 (true d mean/max 0.64/0.67, 0 > 0.80 m); stop_verification 1; contact 5 | strict 10/10; SUCCESS 10 (true d mean/max 0.62/0.66, 0 > 0.80 m); stop_verification 0; contact 5 |
| stop sign | strict 0/15; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 | strict 0/15; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 |
