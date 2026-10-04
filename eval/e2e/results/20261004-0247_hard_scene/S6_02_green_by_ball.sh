#!/bin/bash
cd /tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/int
export PS1='$ '
export E2E_TRACE_FILE=/tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/int/eval/e2e/results/20261004-0247_hard_scene/S6_02_green_by_ball.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh main.py --gui --scene hard --gt-instance '"'"'green_chair#2'"'"''
eval/run_env.sh main.py --gui --scene hard --gt-instance 'green_chair#2' 2>&1 | tee -a /tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/int/eval/e2e/results/20261004-0247_hard_scene/S6_02_green_by_ball.log
sleep 3600
