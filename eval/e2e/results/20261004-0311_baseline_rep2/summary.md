# e2e run `20261004-0311_baseline_rep2`

Commit: `32c6f78` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0311_baseline_rep2/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 34/34 (target 25) | SUCCESS | 17.2 | 0.71 | 0.83 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0311_baseline_rep2/S3_01.mp4` |
| 02 | `find the orange ball` (paraphrase) | ✅ | ✅ | 62/71 (target 44) | SUCCESS | 31.1 | 0.77 | 0.65 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0311_baseline_rep2/S3_02.mp4` |
| 03 | `go to the green chair` | ✅ | ❌ | 71/71 (target 30) | SUCCESS | 15.4 | 0.74 | 0.98 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0311_baseline_rep2/S3_03.mp4` |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 60/60 (target 32) | SUCCESS | 20.0 | 0.72 | 0.85 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0311_baseline_rep2/S3_04.mp4` |
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 15/25 (target 0) | FAIL:target_not_found | 10.8 | None | 3.79 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0311_baseline_rep2/S3_05.mp4` |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 10.9 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0311_baseline_rep2/S3_06.mp4` |
| 07 | `please head over to the orange ball` (paraphrase) | ✅ | ✅ | 31/37 (target 23) | SUCCESS | 16.2 | 0.77 | 0.68 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-0311_baseline_rep2/S3_07.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 21/21 (target 20) | SUCCESS | 17.5 | 0.69 | 0.86 | ✅ | ✅ | ❌ | ✅ | ❌ | `20261004-0311_baseline_rep2/S3_08.mp4` |
| 09 | `go to the red stop sign` | ✅ | ✅ | 15/15 (target 0) | FAIL:target_not_found | 11.0 | None | 1.27 | ❌ | ❌ | ❌ | ❌ | ❌ | `20261004-0311_baseline_rep2/S3_09.mp4` |
| 10 | `go to the blue chair` | ✅ | ✅ | 35/40 (target 0) | FAIL:target_not_found | 10.9 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | `20261004-0311_baseline_rep2/S3_10.mp4` |

**S3 success: 3/10**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
