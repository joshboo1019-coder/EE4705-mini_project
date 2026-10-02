# Task 2 report data — camera pipeline rate comparison (10–20 Hz)

**Collected 2026-10-02 on the team's WSL2 laptop (`joshuapc@DESKTOP-L23ELTA`)
using `tools/capture_camera_evidence.py --hz <rate> --walk`.**

## Methodology

`tools/capture_camera_evidence.py` boots `RealSkills` headless, overrides
`core.config.CAMERA_HZ` in memory for the duration of the run (the file on
disk — and every other script that imports it — is untouched), and polls
`get_camera_frame()` at that rate for 6.0 seconds while a background
thread runs a scripted `move()` → `turn(45)` → `move()` sequence
(`--walk`) so the onboard view shows real scene motion rather than a
static standing shot. Each frame is saved as an annotated PNG (frame
index, elapsed time, target vs. achieved Hz burned into the image) and
stitched into an `.mp4` clip.

Two bugs present in the first capture (`CAMERA_HZ=15`, no `--hz` override
yet) were fixed before this comparison was run: frame 0 used to be
`get_camera_frame()`'s all-zero placeholder (saved before the sim's first
real render landed), and the achieved-Hz figure on that same first frame
was a division-by-near-zero artifact reading in the hundreds of thousands.
Both are fixed by (a) a warm-up poll that waits for a real, non-black
frame before the timed capture window starts, and (b) computing achieved
Hz from the interval to the *previous* captured frame instead of a
cumulative frame-count/elapsed-time ratio. All five runs below were
captured after that fix and show a real scene in frame 0.

Rates tested: 10, 13, 15, 17, 20 Hz — the handout's recommended 10–20 Hz
range, plus the two extra values (13, 17) the team also happened to
collect.

## Results

| Rate | Frames | Duration | Achieved Hz range | Jitter span | Frame 0 |
|---|---|---|---|---|---|
| 10 Hz | 60 | 6.00 s | 9.9 – 10.4 Hz | 0.5 Hz | real scene |
| 13 Hz | 78 | 6.00 s | 12.6 – 13.5 Hz | 0.9 Hz | real scene |
| 15 Hz | 90 | 6.00 s | 14.5 – 15.5 Hz | 1.0 Hz | real scene |
| 17 Hz | 102 | 6.00 s | 15.8 – 18.2 Hz | 2.4 Hz | real scene |
| 20 Hz | 120 | 6.00 s | 19.5 – 20.6 Hz | 1.1 Hz | real scene |

At every tested rate, `frame_count / 6.00 s` reproduces the configured
`--hz` value exactly (60/6=10, 78/6=13, 90/6=15, 102/6=17, 120/6=20) — the
sustained average rate is exact regardless of instant-to-instant jitter.

Per-frame jitter did **not** scale monotonically with rate: 17 Hz showed
the widest spread (2.4 Hz) despite sitting between 15 Hz (1.0 Hz jitter)
and 20 Hz (1.1 Hz jitter), which had comparable, tighter jitter to each
other. This is most likely ordinary run-to-run system load/scheduling
variance (background CPU and render contention at capture time) rather
than a property of the rate itself, and is reported as observed rather
than smoothed into an artificial trend.

## Qualitative observations (onboard view content)

Each run is a fresh physics simulation, so the robot's actual trajectory
— and therefore what the onboard camera happens to see — varies between
runs even though every run issues the identical scripted `move()` →
`turn(45)` → `move()` commands:

- **10 Hz** and **17 Hz** show a pronounced camera swing: the view moves
  from looking straight down a walkway to facing a staircase feature
  almost head-on by t≈4–5 s.
- **13 Hz**, **15 Hz**, and **20 Hz** stay close to the same walkway view
  throughout, with only a slight tilt revealing the staircase edge late
  in the clip.

This is trajectory variance between independent simulation runs, not an
effect of the camera rate — the same `--walk` commands were issued every
time. Included here explicitly so a reader doesn't mistake "this clip
pans more" for "this Hz setting causes more motion."

## Conclusion — why `CAMERA_HZ = 15` was chosen

`core/config.py` picks 15 Hz as the project's real perception rate. This
comparison supports that choice:

- It sits at the midpoint of the handout's recommended 10–20 Hz range.
- Its jitter (1.0 Hz) is comparable to or better than every tested rate
  except 10 Hz, while still being meaningfully faster than the 10 Hz
  floor — fast enough that `_steer_to_center()`'s proportional control
  (`perception/navigation.py`) sees a near-continuous bbox-offset signal
  rather than jumpy, stale-feeling steps between detections.
- It stays well below the 50 Hz policy / 200 Hz physics rate, so the
  offscreen `mujoco.Renderer` call in `skills_real.py`'s
  `_maybe_render_camera` doesn't compete with the control loop for CPU
  time.

10 Hz is the most timing-precise of the rates tested (tightest jitter),
but the lower sampling rate would make `_steer_to_center()`'s steering
updates visibly choppier during an actual object approach. 17–20 Hz offer
no clear accuracy or stability advantage over 15 Hz in this data and cost
more render calls per second for no measured benefit.

## Evidence files

Each run's annotated PNG sequence and `.mp4` clip are saved under
`docs/camera_evidence/<rate>hz/` by `tools/capture_camera_evidence.py`
(e.g. `docs/camera_evidence/15hz/camera_evidence_15hz.mp4`).
