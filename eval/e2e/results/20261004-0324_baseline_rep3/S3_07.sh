#!/bin/bash
cd /tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/base
export PS1='$ '
export E2E_TRACE_FILE=/tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/base/eval/e2e/results/20261004-0324_baseline_rep3/S3_07.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh eval/e2e/drivers/scenario_main.py --gui --scenario 7'
eval/run_env.sh eval/e2e/drivers/scenario_main.py --gui --scenario 7 2>&1 | tee -a /tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/base/eval/e2e/results/20261004-0324_baseline_rep3/S3_07.log
sleep 3600
