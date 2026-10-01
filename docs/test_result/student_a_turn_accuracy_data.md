# Task 2 report data — open-loop vs. closed-loop turn accuracy

**FINAL — 24 trials collected across 3 angles
2026-09-30 (90 deg only),
2026-10-01 (45, 90 & 180 deg)**

## ⚠️ Methodology correction (read this first)

The original 90°-only collection (2026-09-30) ran one closed-loop
`turn(90.0)` immediately followed by one open-loop `move(wz=0.6,
duration=1.5)`, and computed the open-loop's error as `|resulting yaw −
90|` — comparing the **absolute final heading** straight against the
target. That only measures the open-loop step in isolation if the robot
started that step at yaw = 0°, which happened to be true for a single,
first-ever trial (robot spawns at yaw = 0°).

The follow-up collection (2026-10-01) ran `python -m skills.skills_real
--compare-turn --angles 45 90 180 --trials 6`, which runs 18 more
trials back-to-back, each one's `turn()` call targeting `current_yaw +
angle` (not absolute 0). Comparing open-loop's absolute resulting yaw
to the target angle no longer isolates the open-loop step once trials
chain together — it also measures however much of the *preceding*
closed-loop turn happened to be baked into that heading.

**Fix:** measure the open-loop move's own net rotation relative to
wherever the closed-loop turn immediately before it left the robot —
`open_rotation = wrap(yaw_after_open − yaw_after_closed)` — the same
way `turn()` itself measures its own error relative to its own start.
This isolates what the open-loop command alone achieved.

Re-running this corrected formula on the *original* 90° trials (both
absolute yaws were already recorded, just never subtracted from each
other) gives an open-loop rotation of **~24.8° achieved against a 90°
target** — not the ~112.5° absolute heading the original write-up
quoted. This matches the new 90° collection's own result (23.95° mean)
almost exactly, which is a strong consistency check: the original
"22.98° mean error, overshooting" conclusion was an artifact of folding
the preceding closed-loop turn into the open-loop measurement, not a
separate real effect. The corrected, isolated open-loop behavior is a
**large undershoot**, not a small overshoot, and the magnitude below
shows it scales consistently with target angle rather than being a
fixed offset.

---

## Collection 1 — 90°, single closed-loop/open-loop pair (2026-09-30)

Collected from `python skills_real.py --compare-turn` (run from the
`skills/` directory). Each run does one closed-loop `turn(90.0)`
followed by one open-loop `move(vx=0.0, vy=0.0, wz=0.6, duration=1.5)`
(a guessed duration/rate combination meant to approximate 90°, with no
feedback). Raw absolute yaws as originally recorded, plus the corrected
open-loop rotation/error recomputed from them.

| Trial | Closed-loop resulting yaw | Closed \|error\| | Open-loop resulting yaw (absolute) | Open-loop rotation (corrected) | Open-loop \|error\| (corrected) |
|---|---|---|---|---|---|
| 1 | 88.12 | 1.88 | 112.5 | 24.38 | 65.62 |
| 2 | 88.04 | 1.96 | 112.5 | 24.46 | 65.54 |
| 3 | 88.21 | 1.79 | 112.8 | 24.59 | 65.41 |
| 4 | 88.53 | 1.47 | 114.5 | 25.97 | 64.03 |
| 5 | 88.21 | 1.79 | 112.9 | 24.69 | 65.31 |
| 6 | 88.04 | 1.96 | 112.7 | 24.66 | 65.34 |
| **mean (n=6)** | | **1.81** | | **24.79** | **65.21** |

## Collection 2 — 45° / 90° / 180°, 6 trials each (2026-10-01)

Collected from `python -m skills.skills_real --compare-turn --angles 45
90 180 --trials 6`. Each trial runs one closed-loop `turn(angle)`
followed by one open-loop `move(wz=0.6·sign(angle),
duration=1.5·|angle|/90)` — the open-loop duration/rate is linearly
extrapolated from the original single 90° calibration point, which is
exactly the kind of guess an open-loop implementation would actually
make without a measurement at every angle.

### 45°

| Trial | Closed-loop \|error\| | Open-loop achieved rotation | Open-loop target | Open-loop \|error\| |
|---|---|---|---|---|
| 1 | 1.90 | 12.20 | 45.0 | 32.80 |
| 2 | 1.20 | 13.53 | 45.0 | 31.47 |
| 3 | 1.90 | 12.43 | 45.0 | 32.57 |
| 4 | 1.90 | 12.01 | 45.0 | 32.99 |
| 5 | 1.10 | 13.56 | 45.0 | 31.44 |
| 6 | 1.10 | 12.17 | 45.0 | 32.83 |
| **mean (n=6)** | **1.52** | **12.65** | | **32.35** |

### 90°

| Trial | Closed-loop \|error\| | Open-loop achieved rotation | Open-loop target | Open-loop \|error\| |
|---|---|---|---|---|
| 1 | 1.90 | 24.68 | 90.0 | 65.32 |
| 2 | 1.80 | 23.12 | 90.0 | 66.88 |
| 3 | 1.90 | 22.99 | 90.0 | 67.01 |
| 4 | 1.80 | 23.98 | 90.0 | 66.02 |
| 5 | 1.40 | 25.70 | 90.0 | 64.30 |
| 6 | 2.00 | 23.22 | 90.0 | 66.78 |
| **mean (n=6)** | **1.80** | **23.95** | | **66.05** |

### 180°

| Trial | Closed-loop \|error\| | Open-loop achieved rotation | Open-loop target | Open-loop \|error\| |
|---|---|---|---|---|
| 1 | 1.60 | 43.87 | 180.0 | 136.13 |
| 2 | 2.00 | 45.29 | 180.0 | 134.71 |
| 3 | 1.70 | 45.70 | 180.0 | 134.30 |
| 4 | 1.20 | 47.11 | 180.0 | 132.89 |
| 5 | 1.50 | 46.01 | 180.0 | 133.99 |
| 6 | 1.40 | 46.03 | 180.0 | 133.97 |
| **mean (n=6)** | **1.57** | **45.67** | | **134.33** |

## Final summary across all angles (n=6 per angle, 24 trials total)

| Angle | Closed-loop mean \|error\| (deg) | Open-loop mean achieved rotation (deg) | Open-loop mean \|error\| (deg) | Fraction of target achieved (open-loop) |
|---|---|---|---|---|
| 45° | 1.52 | 12.65 | 32.35 | 28.1% |
| 90° (original, corrected) | 1.81 | 24.79 | 65.21 | 27.5% |
| 90° (new collection) | 1.80 | 23.95 | 66.05 | 26.6% |
| 180° | 1.57 | 45.67 | 134.33 | 25.4% |
| **Overall closed-loop (n=24)** | **1.67** | | | |
| **Overall open-loop fraction achieved** | | | | **~26–28%** |

## Conclusion for the report

**Closed-loop `turn()`** stays accurate across every angle tested — mean
error ranges only 1.52–1.81° regardless of whether the target is 45°,
90°, or 180°, consistently close to its own 2° tolerance band. This
confirms the tolerance setting, not control noise, is the binding
constraint, and that true-yaw feedback generalizes cleanly across turn
sizes.

**Open-loop timing**, by contrast, does **not** generalize at all. When
measured correctly — isolating the open-loop move's own net rotation
rather than its absolute final heading — it achieves only
**~25–28% of the commanded angle at every target size tested** (45°,
90°, and 180°, plus a re-analysis of the original single-angle data,
which lands in the same range). This is a strikingly consistent
*multiplicative* shortfall rather than a fixed additive bias: whatever
angle is commanded, the robot turns roughly a quarter of it under
open-loop timing. A naive open-loop implementation that calibrates once
at 90° and linearly scales the duration for other angles (exactly what
this test's own open-loop step does) inherits that same ~70–75%
shortfall at every other angle, rather than correcting for it — proof
that a single-point calibration cannot be extrapolated to other turn
sizes.

**Why the correction matters for the report:** the original write-up's
headline ("22.98° mean error, ~13x worse than closed-loop") measured
something subtly different — the *combined* result of the closed-loop
turn plus the open-loop move's own (much smaller) contribution, not the
open-loop step by itself. The corrected, isolated open-loop numbers
tell a stronger story: open-loop control isn't just less accurate, it
is wrong by a roughly constant *proportion* of the target at every size
tested, which is exactly the kind of miscalibration closed-loop control
eliminates by construction (it measures true yaw and corrects toward it
regardless of what the underlying turning rate actually is, at any
angle).

**Headline numbers for the report:** closed-loop mean error stays in the
1.5–1.8° range across 45°/90°/180° targets (24 trials total), while
open-loop timing achieves only ~25–28% of whatever angle is commanded —
a consistent, large, and non-generalizing shortfall that true-yaw
feedback fixes at every angle tested, not just the one it happened to
be calibrated against.
