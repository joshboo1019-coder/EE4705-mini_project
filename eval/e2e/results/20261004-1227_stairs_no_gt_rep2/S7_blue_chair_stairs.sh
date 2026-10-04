#!/bin/bash
cd /tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/nogt
export PS1='$ '
export E2E_TRACE_FILE=/tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/nogt/eval/e2e/results/20261004-1227_stairs_no_gt_rep2/S7_blue_chair_stairs.trace.jsonl
printf '$ %s\n' 'eval/run_env.sh tools/visual_test_blue_chair_stairs.py'
eval/run_env.sh tools/visual_test_blue_chair_stairs.py 2>&1 | tee -a /tmp/claude-1000/-home-jiamo-EE4705-EE4705-mini-project/ab620e83-df18-4d02-b2c1-c8dc233c4674/scratchpad/wt/nogt/eval/e2e/results/20261004-1227_stairs_no_gt_rep2/S7_blue_chair_stairs.log
sleep 3600
