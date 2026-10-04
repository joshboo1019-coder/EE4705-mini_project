#!/bin/bash
cd /home/jiamo/EE4705/EE4705-mini_project/.worktrees/iter2
export PS1='$ '
export E2E_TRACE_FILE=/home/jiamo/EE4705/EE4705-mini_project/.worktrees/iter2/eval/e2e/results/20261004-1517_iter2_signs_r1/S3_06.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh main.py --gui --scenario 6'
eval/run_env.sh main.py --gui --scenario 6 2>&1 | tee -a /home/jiamo/EE4705/EE4705-mini_project/.worktrees/iter2/eval/e2e/results/20261004-1517_iter2_signs_r1/S3_06.log
sleep 3600
