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

## Scaled comparison (n≈30)

2026-10-04, branch `docs/vlm-scaled`, Student B. Offline only: no simulator run, no control-code change. Script:
`tools/vlm_scaled_eval.py` (`run`, then `report`). Per-frame results: `docs/report_assets/final/vlm_vs_yolo_scaled.csv`;
raw YOLO boxes and VLM answers: `eval/results/vlm/scaled/results.jsonl`.

**Frames (31, all onboard 640×480 `dog_front_camera`).** The e2e run folders don't hold onboard frames:
`eval/e2e/results/*/frames/` and `~/Videos/e2e/*_raw/**/frames/` are empty or hold the 960×540 screen-recording
frame (terminal + third-person GUI view) of each clip, and the close-range frames at the S3 stops were never saved,
only their `[DETECT]` lines. So the set mixes two sources:

- **12 real runtime frames**, saved by the robot's own camera path during real-sim sessions: the 3 frames of the
  live look check above, the third S4 look of e2e run `20261004-0101_baseline`, the 2 VLM probe frames
  (`task3_eval.md`, "VLM choice"), and the 6 Task 2 camera-evidence frames
  (`docs/report_assets/task2/yolo_screenshots/raw/`, incl. the yellow sign at 1.8 m and the red chair at 1.6 m).
  The other 21 saved look frames are the same three scripted S4 poses in later runs, so they were left out as
  near-duplicates. **These are labelled by hand from the image** (Student B): "expected" = clearly visible;
  objects cut by the frame edge or mostly hidden (e.g. the half-hidden ball behind the red sign's pole) are
  "marginal": not required, and not a false positive if reported.
- **19 rendered frames** from the main scene (square "+" sign plates), made earlier with
  `tools/task4_color_testset.py render` (runtime robot, lighting and camera; trunk teleported to views around each
  object). They stand in for the S3 goal views: 9 **stop-sign** views (S3_05/06/09 targets; red, yellow and green
  sign at 1.1, 1.4–1.7 and 2.3–2.5 m), 6 **close-range red chair** views (S3_01/04 target at 0.8 m, the
  closest rendered range; includes the view where yolo11n says "bed"), 2 green-chair, 1 blue-chair and 1 ball view.
  The pick is stratified and seeded (`random.Random(4705)`). **Labels are geometric:** an object is expected if its
  segmentation mask has ≥ 400 visible pixels in the frame (1–399 px = marginal). Sign views start at 1.1 m: at
  0.8 m the plate (z = 0.85 m) is above the camera's view and only the grey pole is in frame.

**Scoring.** One YOLO pass per frame, `RealPerception.detect` with the Task 4 config (`yolo11n.pt`, conf 0.2,
imgsz 736, current colour grounding). One VLM call per frame: `qwen3-vl-flash` through the project's client
(`dialogue.vlm.VLM_SERVICES`, `llm_parser._get_client`, `vlm._png_data_url`), with a detection prompt instead of the
free-text QA prompt: list the objects (not floor, sky or terrain) as JSON `{label, color, bbox}`. A hit needs class
**and** colour. VLM labels are mapped by keyword: chair/seat → chair; sign/flag/plate/board → stop sign (the
scene's only signs are the three "stop signs"); ball/sphere → sports ball. False positive (FP) = a task
class + colour that isn't in the frame. Wrong-class label = any other label: for YOLO every non-task COCO class
(the scene has none of them); for the VLM, labels other than scene structure (pole, stairs, platform are not
counted). bboxes are logged but not scored.

| Object (class + colour) | n visible | YOLO recall | VLM recall |
|---|---|---|---|
| red chair | 16 | 11/16 (69%) | 15/16 (94%) |
| green chair | 10 | 2/10 (20%) | 9/10 (90%) |
| blue chair | 6 | 4/6 (67%) | 6/6 (100%) |
| orange sports ball | 6 | **6/6 (100%)** | 3/6 (50%) |
| red stop sign | 8 | 0/8 (0%) | 8/8 (100%) |
| yellow stop sign | 11 | 0/11 (0%) | 11/11 (100%) |
| green stop sign | 13 | 0/13 (0%) | 13/13 (100%) |
| **all** | **70** | **23/70 (33%)**, Wilson 95% [0.23, 0.44] | **65/70 (93%)**, [0.84, 0.97] |

| Errors (31 frames) | YOLO | VLM |
|---|---|---|
| False positives (class + colour not in the frame) | 1 ("yellow chair" for a far green chair) | 4 (ball called **yellow** ×3, a "blue sign" in a far cluttered view) |
| Wrong-class labels | 6: bed, bench, umbrella, airplane, traffic light | 3: "table" (edge of the red chair), "barrel" (green chair behind a sign), "block" |

| Subset | n frames | n objects | YOLO | VLM |
|---|---|---|---|---|
| **Stop-sign frames** (signs only) | 10 | 13 | 0/13 (0%) | 13/13 (100%) |
| Signs in all frames | 31 | 32 | 0/32 (0%) | 32/32 (100%) |
| **Close-range red chair** (0.8 m, the red chair) | 6 | 6 | 2/6 (33%) | 6/6 (100%) |
| Close-range red chair (all objects in those frames) | 6 | 12 | 4/12 (33%) | 11/12 (92%) |
| Real runtime frames | 12 | 26 | 8/26 (31%) | 25/26 (96%) |
| Rendered frames | 19 | 44 | 15/44 (34%) | 40/44 (91%) |

- **Stop signs.** yolo11n never labels the "+" plates as "stop sign" (once as "traffic light"), the same result as
  the 7/387 in `docs/task4_color_grounding.md`. The VLM finds every sign plate with the right colour, but calls it a
  "sign" or "flag", not a "stop sign". The class match comes from the keyword mapping, which is fair here only
  because the scene has no other signs.
- **Close-range red chair.** At 0.8 m the chair fills the lower frame. Per view, YOLO gives: "bed" red 0.47; "chair"
  red + "bench"; only the ball; nothing; "chair" red; "chair" **blue** 0.21. So it gets "red chair" in 2 of the 6.
  The VLM says "red chair" in all 6. The e2e logs show the same failure at the real stops, e.g. `class=bed color=red conf=0.47` in
  `20261004-0128_p2b_c2_margin_v2/S3_01.log` and `20261004-0118_p2b_c2_margin/S3_04.log`.
- **Where YOLO is better.** The orange ball: YOLO 6/6, VLM 3/6. The VLM calls it yellow in 2 of the misses (and in
  1 frame where it's marginal), and leaves it out of a close red-chair view once. YOLO also gives a usable bbox and
  range, while the VLM boxes aren't checked here.
- **Latency and cost.** YOLO: median 0.007 s per frame (local GPU, after warm-up), p90 0.014 s. VLM: median
  1.15 s, p90 2.33 s, max 3.39 s, about 2× the free-text look calls above, because the JSON answer is longer
  (470 / 121 tokens in / out on average). **Total VLM spend: $0.0022 for 31 calls** ($0.000072 per frame), at the
  price given above.

**Caption** (also in `docs/report_assets/final/CAPTIONS.md`, manual additions): `vlm_vs_yolo_scaled.png` shows recall (class + colour) of YOLO
(yolo11n, conf 0.2, imgsz 736, perception_real colour grounding) vs the VLM (qwen3-vl-flash, one JSON-detection
call per frame) on 31 onboard 640×480 dog_front_camera frames (12 saved by real-sim runs, hand-labelled; 19 rendered
from the main scene with tools/task4_color_testset.py, labelled from segmentation pixel counts), 70 visible objects.
The left panel is per object and the right panel per subset (n = objects). The legend gives false positives and
wrong-class labels. Source: docs/report_assets/final/vlm_vs_yolo_scaled.csv (tools/vlm_scaled_eval.py).

**Limitations.**
- n = 31 frames and 70 object instances. Objects in the same frame aren't independent, so the Wilson intervals are
  only indicative. Each frame got one VLM call at temperature 0, so run-to-run variance isn't measured.
- 19 of the 31 frames are rendered views, not frames from the e2e runs. They use the runtime camera and scene, but
  the poses are set (standing, level trunk) rather than taken from a walk. The close-range set is 0.8 m from the
  chair centre, a little farther than the real S3 stops (true 0.57–0.64 m).
- The real frames are labelled by hand by one person, and the 6 Task 2 frames were framed to show one object.
- The VLM was asked to list the objects it sees, and its labels were mapped to the 3 task classes by keyword. YOLO
  has to pick from 80 COCO classes. That makes this a test of "what is in view, in which colour" (what `look`
  answers), not of `goto_object` detection. The VLM gives no range and takes ~1 s per call, so YOLO stays the
  navigation detector, as in the 3-frame check above.
- The rendered frames live in a scratch folder and aren't committed. Regenerate them with
  `MUJOCO_GL=egl python tools/task4_color_testset.py render --out DIR/tune` and `... render --out DIR/hold
  --holdout`, then `python tools/vlm_scaled_eval.py run --render-dir DIR` (frame ids are in the CSV).
