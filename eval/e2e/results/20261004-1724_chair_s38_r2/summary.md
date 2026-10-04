# e2e run `20261004-1724_chair_s38_r2`

Commit: `45db551` on `iter/chair-safety`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1724_chair_s38_r2/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 03 | `go to the green chair` | ✅ | ❌ | 70/70 (target 28) | FAIL:stop_verification | 25.5 | None | 0.71 | ❌ | ❌ | ✅ | ❌ | ❌ | 0 / 0 / 0 | – |
| 08 | `go to the blue chair` | ✅ | ✅ | 27/27 (target 25) | SUCCESS | 17.2 | 0.47 | 0.66 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |

**S3 success: 1/2** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
