| # | Target | pre-final (no-GT nav, v5) (n=2) | fix/final (n=3) |
|---|---|---|---|
| 01 | red chair | 1/2 (true d 0.76, 0.21) | 1/3 (true d 0.58, 0.64, 0.62; contact runs target 1, other 0) |
| 02 | orange sports ball | 2/2 (true d 0.67, 0.64) | 3/3 (true d 0.64, 0.67, 0.62; contact runs target 0, other 3) |
| 03 | green chair | 2/2 (true d 0.72, 0.69) | 3/3 (true d 0.67, 0.69, 0.68; contact runs target 0, other 0) |
| 04 | red chair | 1/2 (true d 0.58, 0.68) | 0/3 (true d 0.63, 0.64, 0.61; contact runs target 0, other 0) |
| 05 | yellow stop sign | 0/2 (true d 3.77, 3.78) | 0/3 (true d 3.78, 3.77, 3.78; contact runs target 0, other 0) |
| 06 | green stop sign | 0/2 (true d 5.04, 5.05) | 0/3 (true d 5.05, 5.04, 5.05; contact runs target 0, other 0) |
| 07 | orange sports ball | 2/2 (true d 0.59, 0.64) | 3/3 (true d 0.66, 0.62, 0.65; contact runs target 0, other 0) |
| 08 | blue chair | 2/2 (true d 0.67, 0.62) | 3/3 (true d 0.63, 0.67, 0.65; contact runs target 0, other 0) |
| 09 | red stop sign | 0/2 (true d 1.27, 1.27) | 0/3 (true d 1.27, 1.26, 1.27; contact runs target 0, other 0) |
| 10 | blue chair | 2/2 (true d None, None) | 3/3 (true d None, None, None; contact runs target 0, other 0) |
| | **all** | **12/20** (60 %) | **16/30** (53 %) |

| Class | pre-final (no-GT nav, v5) | fix/final |
|---|---|---|
| chair | strict 6/8; SUCCESS 6 (true d mean/max 0.69/0.76, 0 > 0.80 m); stop_verification 1; contact 1 | strict 7/12; SUCCESS 7 (true d mean/max 0.66/0.69, 0 > 0.80 m); stop_verification 4; contact 1 |
| sports ball | strict 4/4; SUCCESS 4 (true d mean/max 0.64/0.67, 0 > 0.80 m); stop_verification 0; contact 2 | strict 6/6; SUCCESS 6 (true d mean/max 0.64/0.67, 0 > 0.80 m); stop_verification 0; contact 3 |
| stop sign | strict 0/6; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 | strict 0/9; SUCCESS 0 (true d mean/max –, 0 > 0.80 m); stop_verification 0; contact 0 |
