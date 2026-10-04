# e2e run `20261004-1703_chair_s14_r1`

Commit: `9412469` on `iter/chair-safety`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1703_chair_s14_r1/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 36/36 (target 27) | SUCCESS | 38.4 | 0.5 | 0.71 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 56/56 (target 29) | SUCCESS | 25.1 | 0.47 | 0.61 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |

**S3 success: 2/2** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
