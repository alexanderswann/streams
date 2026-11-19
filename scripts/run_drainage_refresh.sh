#!/bin/zsh
# Redo the drainages, the flows and everything drawn from them for one or more areas, after a change to
# 05c_drainages.py, 05b_flow.py, flowlib.py, crossbox.py or 06_map.py: per range 05c and 05b, then the area's map
# and creek profiles.
#   ./run_drainage_refresh.sh lexington_va ne_ct      (logs to data/drainage_<area>.log)
# The reaches and their ids stay; scores change only where a reach's flow does. Stops an area at its first failure and goes on.
# Afterwards: 13_overview.py, 14_portable.py, phone_sync.sh (and publish_site.sh for the website copy).
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
for a in "$@"; do
  LOG=../data/drainage_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  ok=1
  for r in $(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"); do
    echo "== $a/$r 05c_drainages $(date +%H:%M:%S)" >> $LOG
    AREA=$a REGION=$r $PY 05c_drainages.py >> $LOG 2>&1 || { echo "FAILED $a/$r 05c $(date +%H:%M:%S)" >> $LOG; ok=0; break; }
    echo "== $a/$r 05b_flow $(date +%H:%M:%S)" >> $LOG
    AREA=$a REGION=$r $PY 05b_flow.py >> $LOG 2>&1 || { echo "FAILED $a/$r 05b $(date +%H:%M:%S)" >> $LOG; ok=0; break; }
  done
  if (( ok )); then
    for s in 06_map 12_profiles; do
      echo "== $a $s $(date +%H:%M:%S)" >> $LOG
      AREA=$a $PY $s.py >> $LOG 2>&1 || { echo "FAILED $a $s $(date +%H:%M:%S)" >> $LOG; ok=0; break; }
    done
  fi
  (( ok )) && echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
done
