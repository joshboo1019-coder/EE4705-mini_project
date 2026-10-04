#!/bin/bash
cd /home/jiamo/EE4705/EE4705-mini_project
export PS1='$ '
export E2E_TRACE_FILE=/home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0101_baseline/S3_02.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh eval/e2e/drivers/scenario_main.py --gui --scenario 2'
eval/run_env.sh eval/e2e/drivers/scenario_main.py --gui --scenario 2 2>&1 | tee -a /home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0101_baseline/S3_02.log
sleep 3600
