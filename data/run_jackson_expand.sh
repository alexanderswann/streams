#!/bin/zsh
# 2026-11-19: grow Jackson by three boxes (jackson_lake, teton_valley, palisades): their DEM, NHD and OSM first, then
# the whole area's hydrology, drops, mid and late steps (run_rebuild_a.sh).
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOG=../data/expand_jackson.log
echo "== START $(date '+%m-%d %H:%M:%S')" >> $LOG
for r in jackson_lake teton_valley palisades; do
  for s in 01_download_dem 02_download_vectors; do
    echo "== jackson/$r $s $(date +%H:%M:%S)" >> $LOG
    AREA=jackson REGION=$r $PY $s.py >> $LOG 2>&1 || echo "FAILED jackson/$r $s $(date +%H:%M:%S)" >> $LOG
  done
done
echo "== rebuild $(date +%H:%M:%S)" >> $LOG
./run_rebuild_a.sh jackson
echo "== DONE $(date '+%m-%d %H:%M:%S')" >> $LOG
