# e2e run `20261004-0247_hard_scene`

Commit: `13cf12b` on ``. LLM: qwen-flash (config.LLM_SERVICE). Clips: `~/Videos/e2e/20261004-0247_hard_scene/` (recorded).

## S6 — Hard scene (optional; `main.py --gui --scene hard`, docs/hard_scene.md)

Success as S3, but true d is to the INTENDED instance (S6_01: either green chair). True d / went-to / touched are ground truth from the trace, logged only.

| # | Typed | [CMD] line | Mission | Est. d at stop | Went to (true d per instance) | True d intended | C1 | C2 true | Not-in-scene detections | Touched | Fall | Success | Clip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01_green_ambiguous | `go to the green chair` | `[CMD] actions=goto_object(class=chair, color=green) n=1` | FAIL:timeout (expected SUCCESS) | None | green_chair#2 {'green_chair#1': 1.24, 'green_chair#2': 0.94} | 0.94 | ❌ | ❌ | orange/chair, unknown/chair | green_chair, green_chair_2 | ✅ | ❌ | `20261004-0247_hard_scene/S6_01_green_ambiguous.mp4` |
| 02_green_by_ball | `go to the green chair next to the orange ball` | `[CMD] actions=goto_object(class=chair, color=green) n=1` | SUCCESS (expected SUCCESS) | 0.54 | green_chair#2 {'green_chair#1': 1.01, 'green_chair#2': 0.78} | 0.78 | ✅ | ✅ | orange/chair, unknown/chair | green_chair | ✅ | ✅ | `20261004-0247_hard_scene/S6_02_green_by_ball.mp4` |
| 03_red_chair_red_box | `go to the red chair` | `[CMD] actions=goto_object(class=chair, color=red) n=1` | SUCCESS (expected SUCCESS) | 0.52 | red_chair {'red_chair': 0.88} | 0.88 | ✅ | ❌ | unknown/chair | red_chair | ✅ | ❌ | `20261004-0247_hard_scene/S6_03_red_chair_red_box.mp4` |
| 04_ball_orange_box | `go to the orange ball` | `[CMD] actions=goto_object(class=sports ball, color=orange) n=1` | SUCCESS (expected SUCCESS) | 0.75 | orange_sports ball {'orange_sports ball': 0.63} | 0.63 | ✅ | ✅ | unknown/chair | red_stop_sign | ✅ | ✅ | `20261004-0247_hard_scene/S6_04_ball_orange_box.mp4` |
| 05_occluded_yellow_sign | `find the yellow stop sign` | `[CMD] actions=goto_object(class=stop sign, color=yellow) n=1` | FAIL:target_not_found (expected FAIL:target_not_found) | None | yellow_stop sign {'yellow_stop sign': 4.89} | 4.89 | ❌ | ❌ | unknown/chair | none | ✅ | ✅ | `20261004-0247_hard_scene/S6_05_occluded_yellow_sign.mp4` |
| 06_red_sign_dim | `go to the red stop sign` | `[CMD] actions=goto_object(class=stop sign, color=red) n=1` | FAIL:target_not_found (expected SUCCESS) | None | red_stop sign {'red_stop sign': 1.27} | 1.27 | ❌ | ❌ | none | none | ✅ | ❌ | `20261004-0247_hard_scene/S6_06_red_sign_dim.mp4` |

**S6 success: 3/6**

- `01_green_ambiguous`: two identical green chairs: which one, and does it switch mid-approach?
- `02_green_by_ball`: spatial qualifier the goto_object schema cannot express: record the parse
- `03_red_chair_red_box`: red box distractor next to the red chair (same rgba)
- `04_ball_orange_box`: orange box distractor next to the ball (same rgba)
- `05_occluded_yellow_sign`: target hidden by wall_north from the spawn (search does not explore)
- `06_red_sign_dim`: control: unoccluded, no distractor, dim light only

## Run notes

- Crashed / never ready: none
- Clips deleted by the frame check: none
