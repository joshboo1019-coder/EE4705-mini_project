| Service | Runs | Accuracy | basic | multi-step | paraphrase | follow-up | chat | invalid | Svc errors | Latency mean / median / p95 (s) | Tokens in / out per call | Cost per call (USD) | Cost per 1k calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen-flash | 3 | 96% (81/84) | 100% | 100% | 88% | 100% | 100% | 100% | 0 | 0.36 / 0.29 / 0.57 | 981 / 29 | 0.000061 | 0.061 |
| gpt-5-nano | 3 | 96% (81/84) | 100% | 100% | 88% | 100% | 100% | 100% | 0 | 0.97 / 0.93 / 1.41 | 968 / 38 | 0.000064 | 0.064 |

Failures (every run):

| Service | Run | Case | Utterance | Got | Why |
|---|---|---|---|---|---|
| qwen-flash | 1 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| qwen-flash | 2 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| qwen-flash | 3 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| gpt-5-nano | 1 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| gpt-5-nano | 2 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |
| gpt-5-nano | 3 | P8 | shuffle sideways to your left for two seconds | `{"action": "move", "vx": 0.0, "vy": -0.8, "wz": 0.0, "duration": 2.0}` | action 1 wrong: move(vx=0, vy=-0.8, 2.0 s) |

Reject reasons given for the invalid cases (all runs):

- **qwen-flash**: X1: impossible:fly; X2: non-English; X3: non-English; X4: empty; X5: out_of_range:duration; X6: unsafe:knock_over; X7: impossible:pick_up; X8: non-English
- **gpt-5-nano**: X1: impossible:fly; X2: non-English; X3: non-English; X4: empty; X5: out_of_range:duration, out_of_range:ten_minutes; X6: unsafe:person; X7: impossible:pick, impossible:picking_up_objects; X8: empty
