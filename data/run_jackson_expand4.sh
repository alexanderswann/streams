#!/bin/zsh
# 2026-11-19, resumed after 04b failed on the Buffalo Fork box (no candidate at all; fixed in 04b_bigcreek_steps.py):
# 03 / 03b / 04 / 04b for all seven boxes are done (run_jackson_expand3.sh, 21:56-22:01; 04b buffalo_fork rerun by hand).
cd /Users/mac/Fishing/scripts
LOG=../data/expand_jackson.log
echo "== resume mid $(date '+%m-%d %H:%M:%S')" >> $LOG
./run_mid.sh jackson
S=$(grep -n '== START jackson' ../data/mid_jackson.log | tail -1 | cut -d: -f1)
if sed -n "$S,\$p" ../data/mid_jackson.log | grep -q "== DONE jackson"; then
  echo "== late $(date +%H:%M:%S)" >> $LOG
  ./run_late.sh jackson
  echo "== DONE relayout $(date '+%m-%d %H:%M:%S')" >> $LOG
else
  echo "FAILED mid: late not run $(date +%H:%M:%S)" >> $LOG
fi
