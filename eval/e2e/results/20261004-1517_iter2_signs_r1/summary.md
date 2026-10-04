# e2e run `20261004-1517_iter2_signs_r1`

Commit: `77eda0d` on `iter/stopsign-plate`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1517_iter2_signs_r1/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 05 | `go to the yellow stop sign` | ✅ | ✅ | 64/71 (target 1) | FAIL:timeout | 120.2 | None | 0.67 | ❌ | ❌ | ✅ | ❌ | ❌ | 31 / 0 / 0 (yellow_stop sign) | – |
| 06 | `go to the green stop sign` | ✅ | ✅ | 10/15 (target 0) | FAIL:target_not_found | 11.0 | None | 5.05 | ❌ | ❌ | ❌ | ❌ | ❌ | 0 / 0 / 0 | – |
| 09 | `go to the red stop sign` | ✅ | ❌ | 3/3 (target 0) | SUCCESS | 11.2 | 0.63 | 0.67 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |

**S3 success: 1/3** · runs with target contact: 1

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
