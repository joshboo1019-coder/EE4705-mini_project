Test set: 33 utterances; each prompt is scored on the cases it was run on (C2 and F3 were added with v3, so v1 and v2 cover 31). Accuracy excludes API errors (calls that still failed after back-off), which are counted separately.

### Prompt v1

| Service | Run 1 | Run 2 | Run 3 | Average | API errors | Latency median / p90 (s) | Tokens in / out per call | Cost per 1k calls (USD) |
|---|---|---|---|---|---|---|---|---|
| qwen-flash | 87.1% (27/31) | 87.1% (27/31) | 87.1% (27/31) | **87.1% (81/93)** | 0 | 0.35 / 0.54 | 980 / 30 | 0.061 |
| gemini-3.8-flash | 100.0% (31/31) | 100.0% (31/31) | 100.0% (31/31) | **100.0% (93/93)** | 0 | 1.81 / 2.41 | 1013 / 31 | 0.874 |
| gpt-5-nano | 93.5% (29/31) | 93.5% (29/31) | 90.3% (28/31) | **92.5% (86/93)** | 0 | 0.93 / 1.22 | 967 / 39 | 0.064 |

| Service | basic | multi-step | paraphrase | lateral | follow-up | chat | invalid |
|---|---|---|---|---|---|---|---|
| qwen-flash | 100.0% | 100.0% | 87.5% | 0.0% | 100.0% | 100.0% | 100.0% |
| gemini-3.8-flash | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| gpt-5-nano | 100.0% | 100.0% | 87.5% | 55.6% | 100.0% | 100.0% | 100.0% |

Failures (v1):

| Service | Run | Case | Utterance | Got | Why |
|---|---|---|---|---|---|
| qwen-flash | 1 | L1 | sidestep to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| qwen-flash | 1 | L2 | shuffle right for one second | `{"action": "move", "vx": 0.0, "vy": 0.8, "wz": 0.0, "duration": 1.0}` | action 1 wrong: move(vx=0, vy=0.8, 1.0 s) |
| qwen-flash | 1 | L3 | slide over to the right a little | `{"action": "move", "vx": 0.0, "vy": 0.3, "wz": 0.0, "duration": 1.5}` | action 1 wrong: move(vx=0, vy=0.3, 1.5 s) |
| qwen-flash | 1 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| qwen-flash | 2 | L1 | sidestep to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| qwen-flash | 2 | L2 | shuffle right for one second | `{"action": "move", "vx": 0.0, "vy": 0.8, "wz": 0.0, "duration": 1.0}` | action 1 wrong: move(vx=0, vy=0.8, 1.0 s) |
| qwen-flash | 2 | L3 | slide over to the right a little | `{"action": "move", "vx": 0.0, "vy": 0.4, "wz": 0.0, "duration": 1.5}` | action 1 wrong: move(vx=0, vy=0.4, 1.5 s) |
| qwen-flash | 2 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| qwen-flash | 3 | L1 | sidestep to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| qwen-flash | 3 | L2 | shuffle right for one second | `{"action": "move", "vx": 0.0, "vy": 0.8, "wz": 0.0, "duration": 1.0}` | action 1 wrong: move(vx=0, vy=0.8, 1.0 s) |
| qwen-flash | 3 | L3 | slide over to the right a little | `{"action": "move", "vx": 0.0, "vy": 0.4, "wz": 0.0, "duration": 1.5}` | action 1 wrong: move(vx=0, vy=0.4, 1.5 s) |
| qwen-flash | 3 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| gpt-5-nano | 1 | L2 | shuffle right for one second | `{"action": "move", "vx": 0.8, "vy": -0.0, "wz": 0.0, "duration": 1.0}` | action 1 wrong: move(vx=0.8, 1.0 s) |
| gpt-5-nano | 1 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| gpt-5-nano | 2 | L1 | sidestep to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| gpt-5-nano | 2 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| gpt-5-nano | 3 | L2 | shuffle right for one second | `{"action": "move", "vx": 0.8, "vy": 0.0, "wz": -1.0, "duration": 1.0}` | action 1 wrong: move(vx=0.8, wz=-1, 1.0 s) |
| gpt-5-nano | 3 | L3 | slide over to the right a little | `{"action": "move", "vx": 0.8, "vy": -0.3, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0.8, vy=-0.3, 2.0 s) |
| gpt-5-nano | 3 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |

### Prompt v2

| Service | Run 1 | Run 2 | Run 3 | Average | API errors | Latency median / p90 (s) | Tokens in / out per call | Cost per 1k calls (USD) |
|---|---|---|---|---|---|---|---|---|
| qwen-flash | 100.0% (31/31) | 100.0% (31/31) | 100.0% (31/31) | **100.0% (93/93)** | 0 | 0.35 / 0.52 | 1164 / 30 | 0.070 |
| gemini-3.8-flash | 100.0% (31/31) | 100.0% (31/31) | 100.0% (31/31) | **100.0% (93/93)** | 0 | 2.03 / 2.34 | 1201 / 31 | 1.017 |
| gpt-5-nano | 100.0% (31/31) | 96.8% (30/31) | 96.8% (30/31) | **97.8% (91/93)** | 0 | 1.02 / 1.23 | 1150 / 39 | 0.073 |

| Service | basic | multi-step | paraphrase | lateral | follow-up | chat | invalid |
|---|---|---|---|---|---|---|---|
| qwen-flash | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| gemini-3.8-flash | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| gpt-5-nano | 100.0% | 100.0% | 91.7% | 100.0% | 100.0% | 100.0% | 100.0% |

Failures (v2):

| Service | Run | Case | Utterance | Got | Why |
|---|---|---|---|---|---|
| gpt-5-nano | 2 | P7 | halt! | `rejected: empty` | rejected (empty) |
| gpt-5-nano | 3 | P7 | halt! | `rejected: invalid_field:actions` | rejected (invalid_field:actions) |

### Prompt v3

| Service | Run 1 | Run 2 | Run 3 | Average | API errors | Latency median / p90 (s) | Tokens in / out per call | Cost per 1k calls (USD) |
|---|---|---|---|---|---|---|---|---|
| qwen-flash | 100.0% (33/33) | 100.0% (33/33) | 100.0% (33/33) | **100.0% (99/99)** | 0 | 0.35 / 0.55 | 1203 / 30 | 0.072 |
| gemini-3.8-flash | 100.0% (33/33) | – | – | **100.0% (33/33)** | 0 | 1.96 / 2.27 | 1240 / 31 | 1.045 |
| gpt-5-nano | 100.0% (33/33) | 100.0% (33/33) | 100.0% (33/33) | **100.0% (99/99)** | 0 | 1.09 / 1.38 | 1189 / 39 | 0.075 |

| Service | basic | multi-step | paraphrase | lateral | follow-up | chat | invalid |
|---|---|---|---|---|---|---|---|
| qwen-flash | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| gemini-3.8-flash | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| gpt-5-nano | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |

Failures (v3):

| Service | Run | Case | Utterance | Got | Why |
|---|---|---|---|---|---|

### Items that flipped between v1 and v2 (passes / runs)

| Service | Case | Utterance | v1 | v2 |
|---|---|---|---|---|
| qwen-flash | P8 | shuffle sideways to your left for two seconds | 0/3 | 3/3 |
| qwen-flash | L1 | sidestep to your left for two seconds | 0/3 | 3/3 |
| qwen-flash | L2 | shuffle right for one second | 0/3 | 3/3 |
| qwen-flash | L3 | slide over to the right a little | 0/3 | 3/3 |
| gpt-5-nano | P7 | halt! | 3/3 | 1/3 |
| gpt-5-nano | P8 | shuffle sideways to your left for two seconds | 0/3 | 3/3 |
| gpt-5-nano | L1 | sidestep to your left for two seconds | 2/3 | 3/3 |
| gpt-5-nano | L2 | shuffle right for one second | 1/3 | 3/3 |
| gpt-5-nano | L3 | slide over to the right a little | 2/3 | 3/3 |

### Items that flipped between v2 and v3 (passes / runs)

| Service | Case | Utterance | v2 | v3 |
|---|---|---|---|---|
| gpt-5-nano | P7 | halt! | 1/3 | 3/3 |

### Logged spend this evaluation (scored calls + follow-up setup turns)

- qwen-flash v2: $0.0065
- qwen-flash v3: $0.0073
- gemini-3.8-flash v1: $0.0813
- gemini-3.8-flash v2: $0.0945
- gemini-3.8-flash v3: $0.0355
- gpt-5-nano v2: $0.0068
- gpt-5-nano v3: $0.0077
