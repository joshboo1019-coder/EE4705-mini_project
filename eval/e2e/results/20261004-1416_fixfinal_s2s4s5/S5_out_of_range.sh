#!/bin/bash
cd /home/jiamo/EE4705/EE4705-mini_project/.worktrees/final
export PS1='$ '
export E2E_TRACE_FILE=/home/jiamo/EE4705/EE4705-mini_project/.worktrees/final/eval/e2e/results/20261004-1416_fixfinal_s2s4s5/S5_out_of_range.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh main.py --gui'
eval/run_env.sh main.py --gui 2>&1 | tee -a /home/jiamo/EE4705/EE4705-mini_project/.worktrees/final/eval/e2e/results/20261004-1416_fixfinal_s2s4s5/S5_out_of_range.log
sleep 3600
