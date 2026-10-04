<!-- [B] S3 on tag final-r3 (n = 3) vs final-r2 (n = 5). Written by Student B. -->
# S3 strict success: final-r3 (n = 3) vs final-r2 (n = 5)

final-r3 = final-r2 + iter/close-range-c1 (re-identify the target on a final label conflict) + prompt v5.1
(iter/state-unseen) + fix/hygiene (harness SIGINT stop, --mock without platform, EOF quit, launch-race readiness
wait) + scaled VLM eval (docs). Runs: `eval/e2e/results/20261004-{1716,1739,1754}_rc_s3_r{1,2,3}` on branch `rc`,
code identical to tag final-r3 (headless `--no-video`; summary.md + results.jsonl only, no raw traces).

**final-r3: 18/30 = 6.0 per run (5, 7, 6), Wilson 95 % [0.42, 0.75]; final-r2: 28/50 = 5.6 per run [0.42, 0.69].**
Target-contact runs: final-r3 1/30 (r1 sc01: chair lost at close range, growing re-acquire strafes pushed the robot
into it, true d 0.24 m — the known re-acquire limitation, fixed on the unmerged iter/chair-safety); final-r2 3/50.
Other-object contact: sc02 touches the red stop sign on the way to the ball in 3/3 (final-r2 5/5).
Not merged (gates failed): iter/chair-safety (sc01+sc04 5/6, 0 target contacts, but sc03/sc08 1/2 each),
iter/avoid (26/30 strict incl. stop signs, but 2 false [FOUND] on sc06 and target/other contacts).

| # | Target | final-r2, n5 (n=5) | final-r3, n3 (n=3) |
|---|---|---|---|
| 01 | red chair | 2/5 (true d 0.58, 0.64, 0.62, 0.68, 0.65; contact runs target 2, other 0) | 1/3 (true d 0.24, 0.6, 0.66; contact runs target 1, other 0) |
| 02 | orange sports ball | 4/5 (true d 0.64, 0.67, 0.62, 0.64, 0.69; contact runs target 0, other 5) | 3/3 (true d 0.61, 0.61, 0.63; contact runs target 0, other 3) |
| 03 | green chair | 5/5 (true d 0.67, 0.69, 0.68, 0.69, 0.72; contact runs target 0, other 0) | 2/3 (true d 0.72, 0.71, 0.68; contact runs target 0, other 0) |
| 04 | red chair | 2/5 (true d 0.63, 0.64, 0.61, 0.66, 0.61; contact runs target 1, other 0) | 3/3 (true d 0.63, 0.62, 0.59; contact runs target 0, other 0) |
| 05 | yellow stop sign | 0/5 (true d 3.78, 3.77, 3.78, 3.79, 3.78; contact runs target 0, other 0) | 0/3 (true d 3.78, 3.77, 3.77; contact runs target 0, other 0) |
| 06 | green stop sign | 0/5 (true d 5.05, 5.04, 5.05, 5.05, 5.03; contact runs target 0, other 0) | 0/3 (true d 5.05, 5.05, 5.06; contact runs target 0, other 0) |
| 07 | orange sports ball | 5/5 (true d 0.66, 0.62, 0.65, 0.64, 0.59; contact runs target 0, other 0) | 3/3 (true d 0.59, 0.66, 0.66; contact runs target 0, other 0) |
| 08 | blue chair | 5/5 (true d 0.63, 0.67, 0.65, 0.65, 0.68; contact runs target 0, other 0) | 3/3 (true d 0.62, 0.68, 0.62; contact runs target 0, other 0) |
| 09 | red stop sign | 0/5 (true d 1.27, 1.26, 1.27, 1.27, 1.27; contact runs target 0, other 0) | 0/3 (true d 1.27, 1.31, 1.27; contact runs target 0, other 0) |
| 10 | blue chair | 5/5 (true d None, None, None, None, None; contact runs target 0, other 0) | 3/3 (true d None, None, None; contact runs target 0, other 0) |
| | **all** | **28/50** (56 %) | **18/30** (60 %) |

| Class | final-r2, n5 | final-r3, n3 |
|---|---|---|
| chair | strict 14/20; SUCCESS 14 (true d mean/max 0.66/0.72, 0 > 0.80 m); stop_verification 4; contact 3 | strict 9/12; SUCCESS 9 (true d mean/max 0.64/0.71, 0 > 0.80 m); stop_verification 2; contact 1 |
| sports ball | strict 9/10; SUCCESS 9 (true d mean/max 0.64/0.67, 0 > 0.80 m); stop_verification 1; contact 5 | strict 6/6; SUCCESS 6 (true d mean/max 0.63/0.66, 0 > 0.80 m); stop_verification 0; contact 3 |
| stop sign | strict 0/15; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 | strict 0/9; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 |
