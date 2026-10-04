# e2e run `20261004-1229_vt4_candidates`

Commit: `f53981e` on `assist/no-gt-height`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1229_vt4_candidates/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 03 | `go to the green chair` | ✅ | ❌ | 64/64 (target 29) | SUCCESS | 15.5 | 0.44 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1229_vt4_candidates/S3_03.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 24/24 (target 22) | SUCCESS | 18.1 | 0.5 | 0.71 | ✅ | ✅ | ✅ | ✅ | ✅ | `20261004-1229_vt4_candidates/S3_08.mp4` |

**S3 success: 2/2**

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
