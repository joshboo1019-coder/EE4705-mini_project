# Bonus — visual QA (`look` action) evaluation

Branch `bonus_b`, 2026-10-02. The VLM is `config.VLM_SERVICE = "qwen3-vl-flash"`. It was chosen from 4 candidates
on two probe frames; that comparison is in `eval/task3_eval.md`, "VLM choice". The parser side (prompt v4, look
cases V1–V8) is also in `eval/task3_eval.md`.

**Setup.** `main.py --gui` on the real custom scene with real skills and YOLO (`yolo11n`, the Task 4 config),
one fresh launch, typed commands. For each `look`, the executor grabs one front-camera frame (640×480). It runs
YOLO on that frame (`[DETECT]` lines), then sends the same frame and the question to the VLM. The robot doesn't
move during a look. Full terminal output: `eval/results/vlm/real_sim_check.log`.

## The 3-frame real-sim check

| # | Pose (x, y, yaw) | Frame | Question | Ground truth in the frame | VLM answer | YOLO `[DETECT]` on the same frame | VLM | YOLO |
|---|---|---|---|---|---|---|---|---|
| 1 | −0.09, 0.01, −176° | `eval/results/vlm/20261002-232010-231387.png` | what can you see? | red chair (left edge, large), red stop sign (centre), green and yellow signs, orange ball half-hidden by the pole, sliver of the green chair (right edge) | "a red chair on the left, a large red square sign on a gray pole in the center, a green … sign … left of center, and a yellow … sign … right of center. The floor is a blue and dark-blue checkered grid …" | `chair color=blue conf=0.50` (the red chair) | ✅ correct, misses the half-hidden ball and the green-chair sliver | ❌ wrong colour on the chair; misses all 3 signs and the ball |
| 2 | −0.08, 0.03, 144° | `eval/results/vlm/20261002-232018-702459.png` | is there a chair in front of you? | green chair (centre-right, fully visible), orange ball, yellow sign, red sign edge | "Yes, there is a green chair in front of you, positioned toward the center-right of the view." | `sports ball color=orange conf=0.73` only | ✅ | ❌ misses the green chair |
| 3 | −0.09, −0.02, −82° | `eval/results/vlm/20261002-232027-560433.png` | what colour is the ball ahead? | open floor, terrain blocks; no ball | "There is no ball visible ahead in the image." | none | ✅ | ✅ |

**The VLM was right 3/3. YOLO was wrong on 2 of the 3 frames.**

## VLM vs YOLO: what went wrong for YOLO

- **Frame 1: the red chair is labelled "blue".** YOLO finds the chair (conf 0.50), but the colour step
  (`perception_real._grounded_color`, the median hue of the inner half of the bbox) mostly sees blue floor and
  sky through the thin chair frame. This matters for Task 4, which must tell the green chair from the red one,
  and "blue" also collides with the scene's real blue chair. The VLM names the colour correctly. The fix is on
  `fix/task4-color-grounding` (`docs/task4_color_grounding.md`).
- **Frame 2: the green chair is missed.** A fully visible chair gets no detection at
  conf ≥ 0.2, while the VLM reports it and where it is ("center-right").
- The VLM has the opposite weakness: it gives no geometry (no bbox, no range), so navigation still needs YOLO.
  It also needs a network round trip. YOLO is local and gives boxes. So the two are complementary: YOLO for
  `goto_object`, the VLM for answering the user's questions.

## Latency and cost per look call

| # | VLM latency (s) | Tokens in / out | VLM cost per call (USD) | Whole command (`[DONE]` t) |
|---|---|---|---|---|
| 1 | 0.96 | 395 / 73 | $0.000049 | 2.7 s (first look of the session; not broken down) |
| 2 | 0.60 | 399 / 22 | $0.000029 | 0.6 s |
| 3 | 0.46 | 397 / 11 | $0.000024 | 0.5 s |
| **mean** | **0.67** | 397 / 35 | **$0.000034** (≈ $0.034 per 1k looks) | |

Price: qwen3-vl-flash, Alibaba Model Studio international (Singapore), 0–32K tier, $0.05 / 1M input and
$0.40 / 1M output tokens (alibabacloud.com/help/en/model-studio/model-pricing, checked 2026-10-03). The image
is billed as about 390 input tokens. The parser call that produced the `look` adds about $0.00008 (qwen-flash,
`eval/task3_eval.md`), so one spoken or typed visual question costs about **$0.0001** end to end.

## Limits

- n = 3 frames, one launch, one VLM. This is a spot check, not an accuracy rate. The probe comparison in
  `task3_eval.md` adds 2 more frames × 4 questions × 4 models.
- The VLM still misses small or occluded things: the half-hidden ball and the green-chair sliver in frame 1.
