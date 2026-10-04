# e2e run `20261004-1857_r7_s3_sc10`

Commit: `15ae7db` on `fix/unseen-goto`. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1857_r7_s3_sc10/` (not recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | `go to the blue chair` | ✅ | ✅ | 34/34 (target 0) | FAIL:target_not_found | 11.1 | None | None | ❌ | ❌ | ❌ | ❌ | ✅ | 0 / 0 / 0 | – |

**S3 success: 1/1** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
