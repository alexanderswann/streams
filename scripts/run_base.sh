#!/bin/zsh
# Base steps for one or more areas: the ones with no area-specific code (DEM, NHD + OSM, hydrology, drops; and the
# flow download the drops need).
#   ./run_base.sh ne_ct central_vt        (run from anywhere; logs to data/base_<area>.log)
# The hydrology is two steps: 03 conditions each box's DEM (with a margin of its neighbours' terrain, so every
# box's DEM must be there first), then 03b works out directions, areas and streams for the whole area at once.
# A failed step is logged and the chain goes on, so one Overpass outage doesn't stop it.
# Re-running is cheap: DEM tiles and NHD downloads already on disk are reused.
# Only one conditioning step runs at a time across chains (pysheds needs several GB on a big box).
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOCK=../data/.hydro.lock
for a in "$@"; do
  LOG=../data/base_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  step() {   # step <range or ""> <script>
    echo "== $a/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG
    if [[ -n $1 ]]; then AREA=$a REGION=$1 $PY $2.py >> $LOG 2>&1; else AREA=$a $PY $2.py >> $LOG 2>&1; fi \
      || echo "FAILED $a/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG
  }
  for r in $ranges; do step $r 01_download_dem; step $r 02_download_vectors; done
  for r in $ranges; do
    until mkdir $LOCK 2>/dev/null; do sleep 10; done
    step $r 03_hydrology
    rmdir $LOCK
  done
  # the flow data before the routing is put together and before the drops: 03b_stitch.py asks NHDPlus's lines which
  # of a lake's outflow lines it drains by (2026-11-22), 04 and 04b count the water crossbox.py carries past dams (a
  # river is a channel from the dam on), and crossbox.py needs the reservoir list and NHDPlus's lines (2026-11-21);
  # run_mid.sh runs it too
  step "" 02b_download_flow
  until mkdir $LOCK 2>/dev/null; do sleep 5; done
  step "" 03b_stitch
  rmdir $LOCK
  for r in $ranges; do step $r 04_knickpoints; step $r 04b_bigcreek_steps; done
  echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
done
