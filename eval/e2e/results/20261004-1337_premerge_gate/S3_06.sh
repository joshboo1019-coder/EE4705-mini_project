#!/bin/bash
cd /home/jiamo/EE4705/EE4705-mini_project
export PS1='$ '
export E2E_TRACE_FILE=/home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-1337_premerge_gate/S3_06.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh main.py --gui --scenario 6'
eval/run_env.sh main.py --gui --scenario 6 2>&1 | tee -a /home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-1337_premerge_gate/S3_06.log
sleep 3600
