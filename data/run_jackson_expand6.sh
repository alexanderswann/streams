#!/bin/zsh
# 2026-11-19: the Buffalo Fork box's drops again after 04b's empty file got numeric columns, then the area-wide end.
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOG=../data/expand_jackson.log
echo "== START bf-fix $(date '+%m-%d %H:%M:%S')" >> $LOG
run() { echo "== jackson/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG
  if [[ -n $1 ]]; then AREA=jackson REGION=$1 $PY $2.py ${@:3} >> $LOG 2>&1; else AREA=jackson $PY $2.py ${@:3} >> $LOG 2>&1; fi \
    || { echo "FAILED jackson/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG; exit 1; }; }
run buffalo_fork 05_score
run buffalo_fork 05c_drainages
run buffalo_fork 05b_flow
run buffalo_fork 08_hike
run buffalo_fork 10_sun
run "" 11_context
run "" watertemp
run "" 06_map
run "" 12_profiles
run "" fish_score_diagram ../output/jackson/fish_score_diagram.png
echo "== DONE bf-fix $(date '+%m-%d %H:%M:%S')" >> $LOG
