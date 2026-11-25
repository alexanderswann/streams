#!/bin/zsh
# run_refresh_late.sh <clone root> <from: 11 | 07> <map> ...   (build-speed, 2026-11-24; the overview's runs, before
# run_promote.sh; a run_*.sh name so the publish guard sees it as a build)
# A batch's test runs its downloads offline (NET_FAIL=1): its maps read the baseline's last good copies, and say so
# ("as of Nov 24" in popups and a legend line) for the layers that carry the wording. This brings a tested clone's late
# layers up to date, online, before promote.py puts the clone into the project:
#   from 11   11_context.py (fires, land, critical habitat, trout surveys and stocking, iNaturalist, gauges, debris
#             flows), watertemp.py, 11b_calendar.py, 06_map.py, 12_profiles.py, fish_score_diagram.py
#   from 07   07_road_closures.py first (the closures and their "as of"); 08_hike.py, 10_sun.py and 09_drive.py again
#             only where the closures came back different (they read road_closures.gpkg and nothing else of 07's;
#             with the same features their outputs would be the same), then the steps of "from 11"
# The steps and their order are run_late.sh's, in the clone's own scripts/ (never the project's), each failure handled
# as run_late.sh does (a download step tried once more after NET_PAUSE; 07, watertemp and 11b_calendar may fail with a
# NOTE; any other failure stops that map). The Adirondack maps run last and adk_northwest last of all: its water-
# temperature fit reads the other three maps' sites (watertemp.py's group fit). Logs: <clone>/data/late_<map>.log.
# One build slot for the whole run, in the critical lane where buildslot.sh has one, given up between maps only to a
# waiting project build (buildslot_yield). Start it by its literal path (the publish guard reads command lines).
# Steps before 07 (02*, 05*, lakes, falls, trails, access roads, OSM names) keep the baseline's copies: promote.py's
# as-of report lists them with their dates.
set -u
clone=${1:?clone root}; from=${2:?from 11 or 07}; shift 2
(( $# )) || { echo "usage: run_refresh_late.sh <clone root> <11|07> <map> ..."; exit 2; }
[[ $from == 11 || $from == 07 ]] || { echo "from: 11 or 07"; exit 2; }
cd $clone/scripts || exit 1
[[ ${PWD:A} == /Users/mac/Fishing/scripts ]] && { echo "STOP: that is the project, not a clone"; exit 1; }
PY=../.venv/bin/python
unset NET_FAIL http_proxy https_proxy HTTP_PROXY HTTPS_PROXY GDAL_HTTP_PROXY      # online: the point of the refresh
export PYTHONDONTWRITEBYTECODE=1
NET_STEPS=(07_road_closures 08_hike 09_drive 11_context watertemp)
NET_PAUSE=${NET_PAUSE:-120}
maps=(${(@)@:#adk_*} ${(@M)@:#adk_*})                               # the Adirondack maps last,
(( ${maps[(Ie)adk_northwest]} )) && maps=(${maps:#adk_northwest} adk_northwest)   # adk_northwest last of all
source ${0:a:h}/buildslot.sh    # the copy beside this script (the project's): the slots are machine-wide, and it has the
export BUILDSLOT_PRIORITY=critical   # critical lane even when the clone's own copy predates it
buildslot_acquire "refresh_late from $from: $maps"

run() {   # run <map> <range or ""> <script> [args]: as run_late.sh's run()
  local try=1
  while true; do
    echo "== $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG
    if [[ -n $2 ]]; then AREA=$1 REGION=$2 $PY $3.py ${@:4} >> $LOG 2>&1; else AREA=$1 $PY $3.py ${@:4} >> $LOG 2>&1; fi \
      && return 0
    if (( try == 1 && ${NET_STEPS[(Ie)$3]} )); then
      echo "RETRY $1/${2:-all} $3 $(date +%H:%M:%S): it downloads; once more in $NET_PAUSE s" >> $LOG
      sleep $NET_PAUSE; try=2
    else
      echo "FAILED $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG; return 1
    fi
  done
}

same_closures() {   # same_closures <old gpkg or ""> <new gpkg>: the same features (columns, values, geometry)
  $PY - "$1" "$2" <<'EOF'
import os, sys
import geopandas as gpd
a, b = sys.argv[1], sys.argv[2]
if not os.path.exists(a) or not os.path.exists(b):
    sys.exit(0 if os.path.exists(a) == os.path.exists(b) else 1)
x, y = gpd.read_file(a), gpd.read_file(b)
same = list(x.columns) == list(y.columns) and len(x) == len(y) and \
    x.drop(columns="geometry").equals(y.drop(columns="geometry")) and \
    list(x.geometry.to_wkb()) == list(y.geometry.to_wkb())
sys.exit(0 if same else 1)
EOF
}

steps() {
  local a=$1 r keep
  local ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  if [[ $from == 07 ]]; then
    keep=$(mktemp -d -t refresh); [[ -f ../output/$a/road_closures.gpkg ]] && cp -c ../output/$a/road_closures.gpkg $keep/
    run $a "" 07_road_closures || echo "NOTE $a: road closures not fetched; continuing without fresh ones" >> $LOG
    if same_closures $keep/road_closures.gpkg ../output/$a/road_closures.gpkg; then
      echo "== $a: the closures' features are the same as the test's: 08_hike, 10_sun and 09_drive stand" >> $LOG
    else
      echo "== $a: the closures changed: 08_hike, 10_sun and 09_drive again" >> $LOG
      for r in $ranges; do run $a $r 08_hike || return 1; run $a $r 10_sun || return 1; done
      run $a "" 09_drive || return 1
    fi
    rm -rf $keep
  fi
  run $a "" 11_context || return 1
  run $a "" watertemp || echo "NOTE $a: no water-temperature fit; the thermal term stays neutral" >> $LOG
  if grep -q 11b_calendar run_late.sh; then
    run $a "" 11b_calendar || echo "NOTE $a: no trout calendar; the popups show none" >> $LOG
  fi
  run $a "" 06_map || return 1
  [[ -f ../output/$a/profiles.html ]] || cp ../output/la/profiles.html ../output/$a/profiles.html
  run $a "" 12_profiles || return 1
  run $a "" fish_score_diagram ../output/$a/fish_score_diagram.png
}

failed=0
for a in $maps; do
  (( ${+functions[buildslot_yield]} )) && buildslot_yield
  LOG=../data/late_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S') (run_refresh_late.sh from $from, online)" >> $LOG
  if steps $a; then echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG; echo "$a refreshed $(date +%H:%M:%S)"
  else failed=1; echo "$a FAILED $(date +%H:%M:%S) (see $clone/data/late_$a.log)"; fi
done
exit $failed
