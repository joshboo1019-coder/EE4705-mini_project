# Task 2 report data — open-loop vs. closed-loop turn accuracy

**FINAL — 6 trials collected, 2026-09-30.**

Collected from `python skills_real.py --compare-turn`. Each run does one closed-loop
`turn(90.0)` followed by one open-loop `move(vx=0.0, vy=0.0, wz=0.6,
duration=1.5)` (a guessed duration/rate combination meant to approximate
90 deg, with no feedback).

Both methods target the same 90.0 deg turn, so `error = |result - 90.0|`.

## Trial 1
| Method | Target (deg) | Resulting yaw (deg) | Extra | `|error|` (deg) |
|--------|--------------|---------------------|-------|--------|--------|
| Closed-loop `turn(90.0)` | 90.0 | 88.12 | printed `final_error=1.9` | 1.88 |
| Open-loop `move(wz=0.6, 1.5s)` | 90.0 | 112.5 | wall_time=2.33s | 22.5 |

## Trial 2
| Method | Target (deg) | Resulting yaw (deg) | Extra | `|error|` (deg) |
|--------|--------------|---------------------|-------|--------|--------|
| Closed-loop `turn(90.0)` | 90.0 | 88.04 | printed `final_error=2.0` | 1.96 |
| Open-loop `move(wz=0.6, 1.5s)` | 90.0 | 112.5 | wall_time=2.41s | 22.5 |

## Trial 3
| Method | Target (deg) | Resulting yaw (deg) | Extra | `|error|` (deg) |
|--------|--------------|---------------------|-------|--------|--------|
| Closed-loop `turn(90.0)` | 90.0 | 88.21 | printed `final_error=1.8` | 1.79 |
| Open-loop `move(wz=0.6, 1.5s)` | 90.0 | 112.8 | wall_time=2.33s | 22.8 |

## Trial 4
| Method | Target (deg) | Resulting yaw (deg) | Extra | `|error|` (deg) |
|--------|--------------|---------------------|-------|--------|--------|
| Closed-loop `turn(90.0)` | 90.0 | 88.53 | printed `final_error=1.5` | 1.47 |
| Open-loop `move(wz=0.6, 1.5s)` | 90.0 | 114.5 | wall_time=2.34s | 24.5 |

## Trial 5
| Method | Target (deg) | Resulting yaw (deg) | Extra | `|error|` (deg) |
|--------|--------------|---------------------|-------|--------|--------|
| Closed-loop `turn(90.0)` | 90.0 | 88.21 | printed `final_error=1.8` | 1.79 |
| Open-loop `move(wz=0.6, 1.5s)` | 90.0 | 112.9 | wall_time=1.82s | 22.9 |

## Trial 6
| Method | Target (deg) | Resulting yaw (deg) | Extra | `|error|` (deg) |
|--------|--------------|---------------------|-------|--------|--------|
| Closed-loop `turn(90.0)` | 90.0 | 88.04 | printed `final_error=2.0` | 1.96 |
| Open-loop `move(wz=0.6, 1.5s)` | 90.0 | 112.7 | wall_time=2.36s | 22.7 |

## Final summary (n=6 each)
| Method | n | mean \|error\| (deg) | min | max | range |
|--------|---|-------|------|-------|-----|-----|-------|
| Closed-loop | 6 | 1.81 | 1.47 | 1.96 | 0.49 |
| Open-loop | 6 | 22.98 | 22.50 | 24.50 | 2.00 |

## Conclusion for the report
Across 6 trials, closed-loop `turn()` (true-yaw feedback, proportional
control, 2 deg tolerance) converged to a mean error of **1.81 deg**
(range 1.47–1.96 deg, spread of only 0.49 deg) — consistently close to
its own tolerance band, meaning the tolerance setting is the binding
constraint, not control noise.

Open-loop `move(wz=0.6, duration=1.5s)` (a fixed timing/rate guess with
no feedback) produced a mean error of **22.98 deg** — roughly **13x**
larger than closed-loop — with results ranging 22.5–24.5 deg. This
error is overwhelmingly a **systematic bias**, not random noise: 5 of 6
trials landed within a 0.4 deg band of each other (112.5, 112.5, 112.7,
112.8, 112.9), with only one outlier (114.5 deg, trial 4, wall_time
2.34s — similar wall-clock time to the other trials, so the outlier
isn't simply explained by timing variance either). This means the
`1.5s @ wz=0.6 -> 90 deg` assumption is consistently *wrong* by a fixed
amount for this platform's real turning dynamics, not merely imprecise
— exactly the kind of miscalibration open-loop control has no way to
detect or correct, and that closed-loop control eliminates by
construction (it measures true yaw and corrects toward it regardless of
what the underlying turning rate actually is).

**Headline numbers for the report:** closed-loop mean error 1.81 deg
vs. open-loop mean error 22.98 deg (n=6 each) — a ~21 deg / ~13x
accuracy improvement from closing the loop on true yaw feedback instead
of trusting a fixed timing assumption.
