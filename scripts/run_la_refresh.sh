#!/bin/zsh
# LA: fresh OpenStreetMap downloads for the ranges that kept old files while Overpass was down (2026-11-18), then
# everything that depends on them. Logs to data/la_refresh.log; stops at the first failure.
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python
LOG=../data/la_refresh.log
ALL=(san_gabriel santa_monica san_bernardino sespe piru sierra_pelona san_jacinto santa_ana_mtns)
STALE=(san_bernardino sespe piru sierra_pelona san_jacinto santa_ana_mtns)
run() {   # run <range or ""> <script>
  echo "== ${1:-all} $2 $(date +%H:%M:%S)" >> $LOG
  if [[ -n $1 ]]; then REGION=$1 $PY $2.py >> $LOG 2>&1; else $PY $2.py >> $LOG 2>&1; fi \
    || { echo "FAILED ${1:-all} $2 $(date +%H:%M:%S)" >> $LOG; exit 1; }
}
echo "== START $(date '+%m-%d %H:%M:%S')" >> $LOG
for r in $STALE; do run $r 02_download_vectors; run $r 05_score; done
run "" 07_road_closures
for r in $ALL; do run $r 05c_drainages; done      # every range's drainages before any range's flow (run_mid.sh)
for r in $ALL; do run $r 05b_flow; done
export REFRESH=1      # the trail and access-road caches date from before the outage too
run "" 02d_trails
run "" 02e_access
unset REFRESH
for r in $ALL; do run $r 08_hike; run $r 10_sun; done
run "" 09_drive; run "" 11_context; run "" watertemp; run "" 06_map; run "" 12_profiles
echo "== DONE $(date '+%m-%d %H:%M:%S')" >> $LOG
