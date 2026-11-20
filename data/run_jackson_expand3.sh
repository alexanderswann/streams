#!/bin/zsh
# 2026-11-19, third pass: the boxes laid out again so no lake lies across an edge between two boxes (config.py):
# 01 + 02 for the six boxes whose extent changed (teton_valley kept its box), then the whole area (run_rebuild_a.sh).
# Downloads run under a time limit: Overpass held connections open for 20+ minutes tonight.
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOG=../data/expand_jackson.log
echo "== START relayout $(date '+%m-%d %H:%M:%S')" >> $LOG
for r in teton_snake gros_ventre hoback jackson_lake buffalo_fork palisades; do
  echo "== jackson/$r 01_download_dem $(date +%H:%M:%S)" >> $LOG
  AREA=jackson REGION=$r perl -e 'alarm shift; exec @ARGV' 1800 $PY 01_download_dem.py >> $LOG 2>&1 || echo "FAILED jackson/$r 01 $(date +%H:%M:%S)" >> $LOG
  for i in 1 2 3; do
    echo "== jackson/$r 02_download_vectors try $i $(date +%H:%M:%S)" >> $LOG
    AREA=jackson REGION=$r perl -e 'alarm shift; exec @ARGV' 900 $PY 02_download_vectors.py >> $LOG 2>&1 && break
    echo "FAILED-OR-TIMED-OUT jackson/$r 02 try $i $(date +%H:%M:%S)" >> $LOG
  done
done
echo "== rebuild $(date +%H:%M:%S)" >> $LOG
./run_rebuild_a.sh jackson
echo "== DONE relayout $(date '+%m-%d %H:%M:%S')" >> $LOG
