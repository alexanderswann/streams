#!/bin/zsh
# Base steps for one or more areas: the ones with no area-specific code (DEM, NHD + OSM, hydrology, drops; and the
# flow download the drops need).
#   ./run_base.sh ne_ct central_vt        (run from anywhere; logs to data/base_<area>.log)
# The hydrology is two steps: 03 conditions each box's DEM (with a margin of its neighbours' terrain, so every
# box's DEM must be there first), then 03b works out directions, areas and streams for the whole area at once.
# A step that downloads and fails is run once more after a pause (NET_STEPS); a step that still fails stops that area
# (the later steps need its output; audit finding 10, 2026-11-22) and the chain goes on to the next area. An Overpass
# outage alone doesn't stop one: 02_download_vectors.py keeps a range's last OSM files then.
# Re-running is cheap: DEM tiles and NHD downloads already on disk are reused.
# Only one conditioning step runs at a time across chains (pysheds needs several GB on a big box): hydrolock.sh.
cd ${0:a:h}          # the scripts folder this driver is in (a scratch copy's own, when it is run from one)
PY=../.venv/bin/python
source ./hydrolock.sh      # locked(): the hydrology lock, let go however the driver ends (2026-11-23)
source ./buildslot.sh      # at most 2 heavy builds at once on this Mac, project builds first; the slot goes when the driver ends
buildslot_acquire "${0:t} $*"
# Steps that download (netfetch.py): one that fails is run once more after NET_PAUSE s (a network drop, a server
# down for a minute) before it counts as failed. With the network down they finish on their last good copies, so a
# failure here means a source with no copy at all (or a fault in the step).
NET_STEPS=(00_area 01_download_dem 02_download_vectors 02b_download_flow 02c_pct 02d_trails 02e_access 02f_known_falls
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

step() {   # step <range or ""> <script>   (area $a, log $LOG)
  local try=1
  skipped $a "$1" $2 && return 0
  while true; do
    echo "== $a/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG
    if [[ -n $1 ]]; then AREA=$a REGION=$1 $PY $2.py >> $LOG 2>&1; else AREA=$a $PY $2.py >> $LOG 2>&1; fi && return 0
    if (( try == 1 && ${NET_STEPS[(Ie)$2]} )); then
      echo "RETRY $a/${1:-all} $2 $(date +%H:%M:%S): it downloads; once more in $NET_PAUSE s" >> $LOG
      sleep $NET_PAUSE; try=2
    else
      echo "FAILED $a/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG
      $PY build_stamp.py failed $a ${1:-all} $2 >> $LOG 2>&1     # the stamp says so (the publish gate reads it)
      return 1
    fi
  done
}

base() {
  local r
  # the area's settings worked out from its outline (crs, boxes, HU4 units, states, sources: area.json), before
  # anything reads config.REGIONS; an area config.py gives every value for goes on with those if this can't download
  step "" 00_area || return 1
  ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  for r in $ranges; do step $r 01_download_dem || return 1; step $r 02_download_vectors || return 1; done
  for r in $ranges; do skipped $a $r 03_hydrology || locked $r 03_hydrology || return 1; done
  # the flow data before the routing is put together and before the drops: 03b_stitch.py asks NHDPlus's lines which
  # of a lake's outflow lines it drains by (2026-11-22), 04 and 04b count the water crossbox.py carries past dams (a
  # river is a channel from the dam on), and crossbox.py needs the reservoir list and NHDPlus's lines (2026-11-21);
  # run_mid.sh runs it too
  step "" 02b_download_flow || return 1
  skipped $a "" 03b_stitch || locked "" 03b_stitch || return 1
  for r in $ranges; do step $r 04_knickpoints || return 1; step $r 04b_bigcreek_steps || return 1; done
}

failed=0
for a in "$@"; do
  LOG=../data/base_$a.log; reached=""
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  if base; then
    echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  else
    echo "== STOPPED $a $(date '+%m-%d %H:%M:%S') at its failed step" >> $LOG; failed=1
  fi
done
exit $failed
