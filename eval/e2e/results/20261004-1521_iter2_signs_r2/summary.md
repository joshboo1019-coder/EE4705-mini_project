# e2e run `20261004-1521_iter2_signs_r2`

Commit: `2f959ad` on `iter/stopsign-plate`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1521_iter2_signs_r2/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 05 | `go to the yellow stop sign` | ✅ | ❌ | 21/21 (target 0) | SUCCESS | 18.5 | 0.67 | 0.74 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 11.0 | None | 5.04 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ❌ | 4/4 (target 0) | SUCCESS | 9.2 | 0.61 | 0.65 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |

**S3 success: 2/3** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
