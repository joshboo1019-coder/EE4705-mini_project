# e2e run `20261004-0324_baseline_rep3`

Commit: `32c6f78` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0324_baseline_rep3/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 35/35 (target 25) | SUCCESS | 13.1 | 0.71 | 0.83 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0324_baseline_rep3/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 69/80 (target 51) | SUCCESS | 30.7 | 0.76 | 0.68 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0324_baseline_rep3/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 62/62 (target 26) | SUCCESS | 13.8 | 0.72 | 0.93 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0324_baseline_rep3/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 64/64 (target 29) | SUCCESS | 23.4 | 0.76 | 0.88 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0324_baseline_rep3/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 10.9 | None | 3.78 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0324_baseline_rep3/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 10.9 | None | 5.05 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0324_baseline_rep3/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 33/34 (target 22) | SUCCESS | 16.3 | 0.73 | 0.64 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0324_baseline_rep3/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 25/25 (target 23) | SUCCESS | 17.0 | 0.76 | 0.99 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0324_baseline_rep3/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 10.9 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0324_baseline_rep3/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 35/37 (target 0) | FAIL:target_not_found | 10.9 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-0324_baseline_rep3/S3_10.mp4` |

**S3 success: 3/10**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
