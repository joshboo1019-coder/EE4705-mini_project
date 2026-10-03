#!/bin/bash
cd /home/jiamo/EE4705/EE4705-mini_project
export PS1='$ '
export E2E_TRACE_FILE=/home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0317_final_rep3/S3_04.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh main.py --gui --scenario 4'
eval/run_env.sh main.py --gui --scenario 4 2>&1 | tee -a /home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0317_final_rep3/S3_04.log
sleep 3600
