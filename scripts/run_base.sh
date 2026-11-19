#!/bin/zsh
# Base steps for one or more areas: the ones with no area-specific code (DEM, NHD + OSM, hydrology, drops).
#   ./run_base.sh ne_ct central_vt        (run from anywhere; logs to data/base_<area>.log)
# A failed step is logged and the range goes on (03 / 04 need only the DEM), so one Overpass outage doesn't stop
# the chain. Re-running is cheap: DEM tiles and NHD downloads already on disk are reused.
# Only one hydrology step runs at a time across chains (pysheds needs several GB on a big box).
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOCK=../data/.hydro.lock
for a in "$@"; do
  LOG=../data/base_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  for r in $(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"); do
    for s in 01_download_dem 02_download_vectors 03_hydrology 04_knickpoints 04b_bigcreek_steps; do
      if [[ $s == 03_hydrology ]]; then until mkdir $LOCK 2>/dev/null; do sleep 10; done; fi
      echo "== $a/$r $s $(date +%H:%M:%S)" >> $LOG
      AREA=$a REGION=$r $PY $s.py >> $LOG 2>&1 || echo "FAILED $a/$r $s $(date +%H:%M:%S)" >> $LOG
      [[ $s == 03_hydrology ]] && rmdir $LOCK
    done
  done
  echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
done
