# e2e run `20261004-1523_iter2_signs_r3`

Commit: `2f959ad` on `iter/stopsign-plate`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1523_iter2_signs_r3/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 05 | `go to the yellow stop sign` | ✅ | ❌ | 22/22 (target 0) | SUCCESS | 17.5 | 0.68 | 0.65 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 35/43 (target 0) | FAIL:timeout | 121.6 | None | 2.83 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 571 / 0 (green_chair) | – |
| 09 | `go to the red stop sign` | ✅ | ❌ | 3/3 (target 0) | SUCCESS | 5.8 | 0.69 | 0.72 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |

**S3 success: 2/3** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
