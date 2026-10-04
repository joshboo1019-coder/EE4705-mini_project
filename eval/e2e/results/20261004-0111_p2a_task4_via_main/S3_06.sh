#!/bin/bash
cd /tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/int
export PS1='$ '
export E2E_TRACE_FILE=/tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/int/eval/e2e/results/20261004-0111_p2a_task4_via_main/S3_06.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh main.py --gui --scenario 6'
eval/run_env.sh main.py --gui --scenario 6 2>&1 | tee -a /tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/int/eval/e2e/results/20261004-0111_p2a_task4_via_main/S3_06.log
sleep 3600
