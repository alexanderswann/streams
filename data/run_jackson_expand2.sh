#!/bin/zsh
# 2026-11-19, resumed after 02f_known_falls hung for 21 min on one Overpass connection (the Smokies run's did too):
# 02f alone with a 15-minute limit, up to three times, then run_mid.sh (whose 02f reads that fresh cache) and run_late.sh.
# 03 / 03b / 04 / 04b for all six boxes were done by run_jackson_expand.sh (19:58-20:02).
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOG=../data/expand_jackson.log
echo "== resume $(date '+%m-%d %H:%M:%S')" >> $LOG
for i in 1 2 3; do
  echo "== jackson/all 02f_known_falls try $i $(date +%H:%M:%S)" >> $LOG
  AREA=jackson perl -e 'alarm shift; exec @ARGV' 900 $PY 02f_known_falls.py >> $LOG 2>&1 && break
  echo "FAILED-OR-TIMED-OUT 02f try $i $(date +%H:%M:%S)" >> $LOG
done
echo "== mid $(date +%H:%M:%S)" >> $LOG
./run_mid.sh jackson
echo "== late $(date +%H:%M:%S)" >> $LOG
./run_late.sh jackson
echo "== DONE $(date '+%m-%d %H:%M:%S')" >> $LOG
