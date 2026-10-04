#!/bin/bash
cd /home/jiamo/EE4705/EE4705-mini_project
export PS1='$ '
export E2E_TRACE_FILE=/home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-1225_stairs_before_gt_rep2/S7_blue_chair_stairs.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh tools/visual_test_blue_chair_stairs.py'
eval/run_env.sh tools/visual_test_blue_chair_stairs.py 2>&1 | tee -a /home/jiamo/EE4705/EE4705-mini_project/eval/e2e/results/20261004-1225_stairs_before_gt_rep2/S7_blue_chair_stairs.log
sleep 3600
