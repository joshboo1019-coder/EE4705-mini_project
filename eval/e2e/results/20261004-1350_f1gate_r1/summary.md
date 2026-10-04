# e2e run `20261004-1350_f1gate_r1`

Commit: `3728dca` on `fix/final`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1350_f1gate_r1/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `` | ❌ | – | None/None (target None) | None | None | None | None | – | – | – | – | ❌ | – | – |
| 04 | `walk over to the red chair` (paraphrase) | ✅ | ✅ | 60/60 (target 30) | SUCCESS | 25.7 | 0.53 | 0.69 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | – |

**S3 success: 1/2** · runs with target contact: 0

## Run notes

- Crashed / never ready: ['S3_01']
- Clips deleted by the frame check: none
