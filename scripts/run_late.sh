#!/bin/zsh
# Last steps for one or more areas, after run_mid.sh: current road closures, approach times, sun, drive times, the
# water-temperature fit, context layers, the maps and the creek profiles.
#   ./run_late.sh ne_ct        (logs to data/late_<area>.log)
# Road closures (07): California's feeds in LA; a keyless feed in four of the other areas (none for NE Connecticut).
# Stops an area at its first failure and goes on to the next area.
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python

run() {   # run <area> <range or ""> <script> [args]
  echo "== $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG
  if [[ -n $2 ]]; then AREA=$1 REGION=$2 $PY $3.py ${@:4} >> $LOG 2>&1; else AREA=$1 $PY $3.py ${@:4} >> $LOG 2>&1; fi \
    || { echo "FAILED $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG; return 1; }
}

steps() {
  local a=$1 r
  local ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  run $a "" 07_road_closures || echo "NOTE $a: road closures not fetched; continuing without fresh ones" >> $LOG
  for r in $ranges; do run $a $r 08_hike || return 1; run $a $r 10_sun || return 1; done
  run $a "" 09_drive || return 1
  run $a "" 11_context || return 1
  run $a "" watertemp || echo "NOTE $a: no water-temperature fit; the thermal term stays neutral" >> $LOG
  run $a "" 06_map || return 1
  [[ -f ../output/$a/profiles.html ]] || cp ../output/la/profiles.html ../output/$a/profiles.html
  run $a "" 12_profiles || return 1
  run $a "" fish_score_diagram ../output/$a/fish_score_diagram.png
}

for a in "$@"; do
  LOG=../data/late_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  steps $a && echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
done
