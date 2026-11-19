#!/bin/zsh
# Rebuild everything derived from the terrain routing for one or more areas, after a change to 03_hydrology.py:
# per range 03 hydrology, 04 / 04b drops, 05 reach scoring; then per range 05c drainages and 05b flow.
#   ./run_rebuild_a.sh la        (logs to data/rebuild_<area>.log; run_late.sh <area> finishes the maps)
# A failed step is logged and the chain goes on. One hydrology step at a time across chains (memory).
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOCK=../data/.hydro.lock
for a in "$@"; do
  LOG=../data/rebuild_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  for r in $ranges; do
    for s in 03_hydrology 04_knickpoints 04b_bigcreek_steps 05_score; do
      if [[ $s == 03_hydrology ]]; then until mkdir $LOCK 2>/dev/null; do sleep 5; done; fi
      echo "== $a/$r $s $(date +%H:%M:%S)" >> $LOG
      AREA=$a REGION=$r $PY $s.py >> $LOG 2>&1 || echo "FAILED $a/$r $s $(date +%H:%M:%S)" >> $LOG
      [[ $s == 03_hydrology ]] && rmdir $LOCK
    done
  done
  for r in $ranges; do
    for s in 05c_drainages 05b_flow; do
      echo "== $a/$r $s $(date +%H:%M:%S)" >> $LOG
      AREA=$a REGION=$r $PY $s.py >> $LOG 2>&1 || echo "FAILED $a/$r $s $(date +%H:%M:%S)" >> $LOG
    done
  done
  echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
done
