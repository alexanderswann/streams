#!/bin/zsh
# Rebuild everything derived from the terrain routing for one or more areas, after a change to 03_hydrology.py or
# 03b_stitch.py: 03 per range, 03b for the area, 04 / 04b drops per range; then run_mid.sh and run_late.sh
# (reach scoring, flow, drainages, trails, approach times, sun, context, the maps and profiles).
#   ./run_rebuild_a.sh la        (logs to data/rebuild_<area>.log, and the mid_ / late_ logs)
#   SKIP_03=1 ./run_rebuild_a.sh la      after a change to 03b_stitch.py only: start at 03b (03's dem_cond.tif, the
#                                        surface 03b routes on, stays as it is)
# The reaches get new ids (they are numbered along the stream network), so every later step runs again.
# A failed hydrology or drop step is logged and the chain goes on. One conditioning step at a time across chains.
# Afterwards: 13_overview.py, 14_portable.py, phone_sync.sh.
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOCK=../data/.hydro.lock
for a in "$@"; do
  LOG=../data/rebuild_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  step() {   # step <range or ""> <script>
    echo "== $a/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG
    if [[ -n $1 ]]; then AREA=$a REGION=$1 $PY $2.py >> $LOG 2>&1; else AREA=$a $PY $2.py >> $LOG 2>&1; fi \
      || echo "FAILED $a/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG
  }
  [[ -n $SKIP_03 ]] || for r in $ranges; do
    until mkdir $LOCK 2>/dev/null; do sleep 5; done
    step $r 03_hydrology
    rmdir $LOCK
  done
  until mkdir $LOCK 2>/dev/null; do sleep 5; done
  step "" 03b_stitch
  rmdir $LOCK
  for r in $ranges; do step $r 04_knickpoints; step $r 04b_bigcreek_steps; done
  echo "== mid $(date +%H:%M:%S)" >> $LOG
  ./run_mid.sh $a
  echo "== late $(date +%H:%M:%S)" >> $LOG
  ./run_late.sh $a
  echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
done
