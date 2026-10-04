# e2e run `20261004-1429_video_task4_tag`

Commit: `1b95477` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-1429_video_task4_tag/` (recorded).

## S3 — Task 4 (C's 10 scenarios, typed utterance)

Success = `[MISSION] status=SUCCESS` and true d ≤ 0.80 m and C1 (scenario 10: the correct `FAIL reason=target_not_found`). True d is ground truth, logged only.

| # | Typed | [CMD] ok | Search | DETECT correct | Mission | Time (s) | Est. d at stop | True d | C1 | C2 est | C2 true | C3 | Success | Contacts (target / other objects / terrain, samples) | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 03 | `go to the green chair` | ✅ | ❌ | 71/71 (target 31) | SUCCESS | 18.1 | 0.45 | 0.68 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | `20261004-1429_video_task4_tag/S3_03.mp4` |
| 08 | `go to the blue chair` | ✅ | ✅ | 24/24 (target 21) | SUCCESS | 19.2 | 0.41 | 0.6 | ✅ | ✅ | ✅ | ✅ | ✅ | 0 / 0 / 0 | `20261004-1429_video_task4_tag/S3_08.mp4` |

**S3 success: 2/2** · runs with target contact: 0

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
