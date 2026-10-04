# e2e run `20261004-1712_chair_s14_r3`

Commit: `9412469` on `iter/chair-safety`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1712_chair_s14_r3/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 34/34 (target 25) | SUCCESS | 30.4 | 0.52 | 0.79 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 57/57 (target 27) | FAIL:stop_verification | 33.4 | None | 0.66 | ❌ | ❌ | ✅ | ❌ | ❌ | 0 / 0 / 0 | – |

**S3 success: 1/2** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
