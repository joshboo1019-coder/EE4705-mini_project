#!/bin/bash
cd /home/jiamo/EE4705/EE4705-mini_project
export PS1='$ '
export E2E_TRACE_FILE=/home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0101_baseline/S4_look.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh main.py --gui'
eval/run_env.sh main.py --gui 2>&1 | tee -a /home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0101_baseline/S4_look.log
sleep 3600
