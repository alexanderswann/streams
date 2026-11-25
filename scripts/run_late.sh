#!/bin/zsh
# Last steps for one or more areas, after run_mid.sh: current road closures, approach times, sun, drive times, the
# water-temperature fit, context layers, the maps and the creek profiles.
#   ./run_late.sh ne_ct        (logs to data/late_<area>.log)
# Road closures (07): California's feeds in LA; a keyless feed in four of the other areas (none for NE Connecticut).
# Stops an area at its first failure and goes on to the next area; exits 1 if any area stopped.
cd ${0:a:h}          # the scripts folder this driver is in (a scratch copy's own, when it is run from one)
PY=../.venv/bin/python
source ./buildslot.sh      # at most 2 heavy builds at once on this Mac, project builds first; the slot goes when the driver ends
buildslot_acquire "${0:t} $*"
# Steps that download (netfetch.py): one that fails is run once more after NET_PAUSE s (a network drop, a server
# down for a minute) before it counts as failed. With the network down they finish on their last good copies, so a
# failure here means a source with no copy at all (or a fault in the step).
NET_STEPS=(01_download_dem 02_download_vectors 02b_download_flow 02c_pct 02d_trails 02e_access 02f_known_falls
           02g_greenness 02h_buried_inputs 05_score 05d_lakes lake_bathymetry 07_road_closures 08_hike 09_drive 11_context watertemp)
NET_PAUSE=${NET_PAUSE:-120}

# FROM=<step> (run_area.sh's second word): the build starts at that step and leaves the steps before it as they are,
# with a line in the log for each; FROM_REACHED names a file that tells a later driver of the same build it was reached.
want() {   # want <step>: true for a step to run
  [[ -z $FROM || -n $reached ]] && return 0
  [[ -n $FROM_REACHED && -e $FROM_REACHED ]] && { reached=1; return 0; }
  [[ $1 == $FROM ]] || return 1
  reached=1; [[ -n $FROM_REACHED ]] && : > $FROM_REACHED
  return 0
}
skipped() {   # skipped <area> <range or ""> <step>: true, with a line in the log, for a step before FROM
  want $3 && return 1
  echo "== $1/${2:-all} $3 skipped (FROM=$FROM)" >> $LOG
}

run() {   # run <area> <range or ""> <script> [args]
  local try=1
  skipped $1 "$2" $3 && return 0
  while true; do
    echo "== $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG
    if [[ -n $2 ]]; then AREA=$1 REGION=$2 $PY $3.py ${@:4} >> $LOG 2>&1; else AREA=$1 $PY $3.py ${@:4} >> $LOG 2>&1; fi \
      && return 0
    if (( try == 1 && ${NET_STEPS[(Ie)$3]} )); then
      echo "RETRY $1/${2:-all} $3 $(date +%H:%M:%S): it downloads; once more in $NET_PAUSE s" >> $LOG
      sleep $NET_PAUSE; try=2
    else
      echo "FAILED $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG
      $PY build_stamp.py failed $1 ${2:-all} $3 >> $LOG 2>&1     # the stamp says so (the publish gate reads it)
      return 1
    fi
  done
}

steps() {
  local a=$1 r
  local ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  run $a "" 07_road_closures || echo "NOTE $a: road closures not fetched; continuing without fresh ones" >> $LOG
  for r in $ranges; do run $a $r 08_hike || return 1; run $a $r 10_sun || return 1; done
  run $a "" 09_drive || return 1
  run $a "" 11_context || return 1
  run $a "" watertemp || echo "NOTE $a: no water-temperature fit; the thermal term stays neutral" >> $LOG
  run $a "" 11b_calendar || echo "NOTE $a: no trout calendar; the popups show none" >> $LOG
  run $a "" 06_map || return 1
  [[ -f ../output/$a/profiles.html ]] || cp profiles.html ../output/$a/profiles.html     # the page; 12_profiles.py writes its data
  run $a "" 12_profiles || return 1
  run $a "" fish_score_diagram ../output/$a/fish_score_diagram.png
}

failed=0
for a in "$@"; do
  LOG=../data/late_$a.log; reached=""
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  if steps $a; then echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG; else failed=1; fi
done
exit $failed
