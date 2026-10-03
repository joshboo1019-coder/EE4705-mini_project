#!/bin/bash
cd /home/jiamo/EE4705/EE4705-mini_project
export PS1='$ '
export E2E_TRACE_FILE=/home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0221_final/S1_move.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh eval/e2e/drivers/s1_task2.py --gui --mode move'
eval/run_env.sh eval/e2e/drivers/s1_task2.py --gui --mode move 2>&1 | tee -a /home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-0221_final/S1_move.log
sleep 3600
