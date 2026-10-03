#!/bin/bash
cd /home/jiamo/EE4705/EE4705-mini_project
export PS1='$ '
export E2E_TRACE_FILE=/home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0101_baseline/S1_open.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh eval/e2e/drivers/s1_task2.py --gui --mode open'
eval/run_env.sh eval/e2e/drivers/s1_task2.py --gui --mode open 2>&1 | tee -a /home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0101_baseline/S1_open.log
sleep 3600
