<!-- [assist C] Stage-4 iteration 1. Change contributed by Student B (assist), pending review by Student C. -->
# iter/close-range-c1 — re-identify the target on a final label conflict

Branch `iter/close-range-c1` (from tag `final`), **not merged**. One change in `perception/navigation.py`
(`_finish_if_found` path): when the final stop check sees YOLO detections but none of them matches the target
("final label conflict not confirmed by target history"), try the tracker's full-live-frame re-identification once
(`recover_target(frame, …)`) before failing C1. C1 stays a live-frame detection; no ground truth.

Why: the most frequent Task-4 failure on tag `final` that was not already disclosed as a limitation is the red
chair (S3 01/04: 4/10, all 6 failures at the stop with true d 0.58–0.65 m), where yolo11n labels the frame-filling
chair "bed".

## Gate (S3 strict, n = 3, headless `--no-video`, runs `eval/e2e/results/*iter1_s3_r{1,2,3}`)

| | tag final (n = 5) | iter1 (n = 3) |
|---|---|---|
| all | 28/50 (16.8 per 3 runs) | **19/30** |
| 01 red chair | 2/5 | 3/3 |
| 02 orange ball | 4/5 | 3/3 |
| 03 green chair | 5/5 | 3/3 |
| 04 red chair | 2/5 | 2/3 |
| 05/06/09 stop signs | 0/15 | 0/9 |
| 07 orange ball | 5/5 | 3/3 |
| 08 blue chair | 5/5 | 2/3 (r1: search `target_not_found`, robot never left the start — not the stop path) |
| 10 absent blue chair | 5/5 | 3/3 |

Gate rule: total ≥ final + 2 (≥ 18.8 of 30) and no scenario worse by > 1/3 → **PASS** (08 is worse by exactly 1/3,
by a search failure unrelated to the change). r1 S3_06 = launch race ("never became ready", known).

Honest reading: the new path fired in 2 of 6 red-chair runs — r2 S3_04 rescued (SUCCESS, true d 0.57 m),
r3 S3_04 still failed. The other red-chair successes never reached the label conflict, so most of the +2 over the
baseline is run-to-run variance; the causal effect measured here is 1 rescue in 6 runs, no false stop.
pytest 283 passed + 1 xfailed. **Verdict: low-risk, merge after Student C's review** (it only acts where the run
would otherwise FAIL, and the re-identification uses the same tracker as the existing recovery path).
