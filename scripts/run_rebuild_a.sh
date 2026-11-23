#!/bin/zsh
# Rebuild everything derived from the terrain routing for one or more areas, after a change to 03_hydrology.py or
# 03b_stitch.py: 03 per range, 03b for the area, 04 / 04b drops per range; then run_mid.sh and run_late.sh
# (reach scoring, flow, drainages, trails, approach times, sun, context, the maps and profiles).
#   ./run_rebuild_a.sh la        (logs to data/rebuild_<area>.log, and the mid_ / late_ logs)
#   SKIP_03=1 ./run_rebuild_a.sh la      after a change to 03b_stitch.py only: start at 03b (03's dem_cond.tif, the
#                                        surface 03b routes on, stays as it is)
#   SKIP_03B=1 ./run_rebuild_a.sh la     after a change to the drops, the reaches or crossbox.py only: start at 04
#                                        (the routing stays as it is)
# The reaches get new ids (they are numbered along the stream network), so every later step runs again.
# A step that downloads and fails is run once more after a pause (NET_STEPS); a step that still fails stops that area,
# its mid and late steps included (audit finding 10, 2026-11-22), and the chain goes on to the next area. One
# conditioning step at a time across chains (hydrolock.sh).
# Afterwards: 13_overview.py, 14_portable.py, phone_sync.sh.
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
source ./hydrolock.sh      # locked(): the hydrology lock, let go however the driver ends (2026-11-23)
# Steps that download (netfetch.py): one that fails is run once more after NET_PAUSE s (a network drop, a server
# down for a minute) before it counts as failed. With the network down they finish on their last good copies, so a
# failure here means a source with no copy at all (or a fault in the step).
NET_STEPS=(01_download_dem 02_download_vectors 02b_download_flow 02c_pct 02d_trails 02e_access 02f_known_falls
           02g_greenness 05_score 05d_lakes lake_bathymetry 07_road_closures 08_hike 09_drive 11_context watertemp)
NET_PAUSE=${NET_PAUSE:-120}

step() {   # step <range or ""> <script>   (area $a, log $LOG)
  local try=1
  while true; do
    echo "== $a/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG
    if [[ -n $1 ]]; then AREA=$a REGION=$1 $PY $2.py >> $LOG 2>&1; else AREA=$a $PY $2.py >> $LOG 2>&1; fi && return 0
    if (( try == 1 && ${NET_STEPS[(Ie)$2]} )); then
      echo "RETRY $a/${1:-all} $2 $(date +%H:%M:%S): it downloads; once more in $NET_PAUSE s" >> $LOG
      sleep $NET_PAUSE; try=2
    else
      echo "FAILED $a/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG; return 1
    fi
  done
}

routing() {
  local r
  [[ -n $SKIP_03 || -n $SKIP_03B ]] || for r in $ranges; do locked $r 03_hydrology || return 1; done
  if [[ -z $SKIP_03B ]]; then
    # 03b_stitch.py asks NHDPlus's lines which of a lake's outflow lines it drains by: fetch them first if they are
    # not there yet (run_mid.sh refreshes the flow data in any case)
    [[ -f ../data/raw/$a/_shared/flow/nhdplus_v2.gpkg ]] || step "" 02b_download_flow || return 1
    locked "" 03b_stitch || return 1
  fi
  for r in $ranges; do step $r 04_knickpoints || return 1; step $r 04b_bigcreek_steps || return 1; done
}

failed=0
for a in "$@"; do
  LOG=../data/rebuild_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  if ! routing; then
    echo "== STOPPED $a $(date '+%m-%d %H:%M:%S') at its failed step; no mid or late steps" >> $LOG; failed=1; continue
  fi
  echo "== mid $(date +%H:%M:%S)" >> $LOG
  if ! ./run_mid.sh $a; then
    echo "== STOPPED $a $(date '+%m-%d %H:%M:%S'): run_mid.sh failed (data/mid_$a.log); no late steps" >> $LOG; failed=1; continue
  fi
  echo "== late $(date +%H:%M:%S)" >> $LOG
  if ! ./run_late.sh $a; then
    echo "== STOPPED $a $(date '+%m-%d %H:%M:%S'): run_late.sh failed (data/late_$a.log)" >> $LOG; failed=1; continue
  fi
  echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
done
exit $failed
