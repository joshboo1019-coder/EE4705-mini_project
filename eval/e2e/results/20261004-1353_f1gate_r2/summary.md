# e2e run `20261004-1353_f1gate_r2`

Commit: `088d938` on `fix/final`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1353_f1gate_r2/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `go to the red chair` | ✅ | ✅ | 57/57 (target 37) | SUCCESS | 89.9 | 0.45 | 0.91 | ✅ | ✅ | ❌ | ✅ | ❌ | 80 / 0 / 0 (red_chair) | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 64/64 (target 29) | SUCCESS | 25.9 | 0.47 | 0.61 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |

**S3 success: 1/2** · runs with target contact: 1

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
