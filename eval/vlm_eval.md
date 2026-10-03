# Bonus — visual QA (`look` action) evaluation

Branch `bonus_b`, 2026-10-02. The VLM is `config.VLM_SERVICE = "qwen3-vl-flash"`. It was chosen from 4 candidates
on two probe frames; that comparison is in `eval/task3_eval.md`, "VLM choice". The parser side (prompt v4, look
cases V1–V8) is also in `eval/task3_eval.md`.

**Setup.** `main.py --gui` on the real custom scene with real skills and YOLO (`yolo11n`, the Task 4 config),
one fresh launch, typed commands. For each `look`, the executor grabs one front-camera frame (640×480). It runs
YOLO on that frame (`[DETECT]` lines), then sends the same frame and the question to the VLM. The robot doesn't
move during a look. Full terminal output: `eval/results/vlm/real_sim_check.log`.

## The 3-frame real-sim check

The live run used `bonus_b`'s copy of `perception/perception_real.py`, which predates Student C's colour fix
on main (`9da795e`, 2026-10-02 22:19). On 2026-10-03, YOLO was re-run offline on the 3 saved frames with the
same settings (`yolo11n`, conf 0.2, imgsz 736; these are identical on `bonus_b` and main). Each box was then
grounded with three versions: the live one ("pre-9da795e"), main's, and `fix/task4-color-grounding`'s. The
boxes and confidences are identical to the live `[DETECT]` lines; only the colour step differs.

| # | Pose (x, y, yaw) | Frame | Question | Ground truth in the frame | VLM answer (live) | VLM |
|---|---|---|---|---|---|---|
| 1 | −0.09, 0.01, −176° | `eval/results/vlm/20261002-232010-231387.png` | what can you see? | red chair (left edge, large), red stop sign (centre), green and yellow signs, orange ball half-hidden by the pole, sliver of the green chair (right edge) | "a red chair on the left, a large red square sign on a gray pole in the center, a green … sign … left of center, and a yellow … sign … right of center. The floor is a blue and dark-blue checkered grid …" | ✅ misses the half-hidden ball and the green-chair sliver |
| 2 | −0.08, 0.03, 144° | `eval/results/vlm/20261002-232018-702459.png` | is there a chair in front of you? | green chair (centre-right, fully visible), orange ball, yellow sign, red sign edge | "Yes, there is a green chair in front of you, positioned toward the center-right of the view." | ✅ |
| 3 | −0.09, −0.02, −82° | `eval/results/vlm/20261002-232027-560433.png` | what colour is the ball ahead? | open floor, terrain blocks; no ball | "There is no ball visible ahead in the image." | ✅ |

| # | YOLO detections (conf ≥ 0.2) | colour: pre-9da795e (live) | colour: main | colour: fix branch | YOLO misses (any colour version) |
|---|---|---|---|---|---|
| 1 | chair conf 0.50, bbox [0, 111, 84, 263] (the red chair) | **blue** ❌ | red ✅ | red ✅ | all 3 signs and the ball; none of them shows up even at conf ≥ 0.05 |
| 2 | sports ball conf 0.73 | orange ✅ | orange ✅ | orange ✅ | **the green chair**: scored 0.14, below the 0.2 threshold |
| 3 | none | – | – | – | nothing to detect ✅ |

**The VLM was right 3/3.** With current code, YOLO is fully right on 1 of the 3 frames (frame 3). It gets the
red chair right but misses objects in frame 1, and misses the green chair in frame 2. In the live run it also
had the chair's colour wrong, but that part was stale code.

## VLM vs YOLO: what YOLO really misses, and what was a stale-code artefact

- **Stale-code artefact: frame 1's red chair → "blue".** It came from the pre-`9da795e` grounding (median hue
  of the bbox's inner half, where the blue floor and sky dominate a thin chair frame). Main and the fix branch
  both say red on the same box. It isn't evidence against YOLO + grounding as they stand now.
- **Real miss: frame 2's green chair.** The chair is fully visible, about centre-right, but YOLO scores it 0.14,
  below `YOLO_CONF_THRESHOLD = 0.2`. The VLM reports it and where it is. This matches the rendered test set in
  `docs/task4_color_grounding.md`: yolo11n finds the green chair in 66% of the views where it is visible.
- **Real miss: the stop signs.** None of the 3 signs in frame 1 is detected at any confidence. That's expected
  for this scene: its signs are square "+" plates, and yolo11n labels a sign "stop sign" in only 7 of 387
  rendered views. The VLM reports all three, as red, green and yellow square/rectangular signs on poles.
- **Real miss: the half-hidden ball** in frame 1. The VLM misses it too.
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
