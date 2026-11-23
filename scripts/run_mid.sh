#!/bin/zsh
# Middle steps for one or more areas, after run_base.sh: reach scoring, flow, drainages, trails and access roads.
#   ./run_mid.sh ne_ct lexington_va        (logs to data/mid_<area>.log)
# Stops an area at its first failure (later steps need the earlier ones) and goes on to the next area; exits 1 if any
# area stopped (run_rebuild_a.sh then skips that area's late steps).
cd ${0:a:h}          # the scripts folder this driver is in (a scratch copy's own, when it is run from one)
PY=../.venv/bin/python
# Steps that download (netfetch.py): one that fails is run once more after NET_PAUSE s (a network drop, a server
# down for a minute) before it counts as failed. With the network down they finish on their last good copies, so a
# failure here means a source with no copy at all (or a fault in the step).
NET_STEPS=(01_download_dem 02_download_vectors 02b_download_flow 02c_pct 02d_trails 02e_access 02f_known_falls
           02g_greenness 05_score 05d_lakes lake_bathymetry 07_road_closures 08_hike 09_drive 11_context watertemp)
NET_PAUSE=${NET_PAUSE:-120}

run() {   # run <area> <range or ""> <script>
  local try=1
  while true; do
    echo "== $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG
    if [[ -n $2 ]]; then AREA=$1 REGION=$2 $PY $3.py >> $LOG 2>&1; else AREA=$1 $PY $3.py >> $LOG 2>&1; fi && return 0
    if (( try == 1 && ${NET_STEPS[(Ie)$3]} )); then
      echo "RETRY $1/${2:-all} $3 $(date +%H:%M:%S): it downloads; once more in $NET_PAUSE s" >> $LOG
      sleep $NET_PAUSE; try=2
    else
      echo "FAILED $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG; return 1
    fi
  done
}

steps() {
  local a=$1 r
  local ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  run $a "" 02f_known_falls || return 1      # known waterfalls from every source, for 05_score's drop names
  # the flow data first: 05_score.py's size floor reads crossbox.py's links past dams, which need the reservoir list
  # and NHDPlus's lines (2026-11-21; it ran after 05_score before, which a new area's first build would trip over)
  run $a "" 02b_download_flow || return 1
  # lakes, for the areas 05d_lakes.py is built for (it says so and does nothing elsewhere), before the reaches: 05_score.py
  # cuts the stream links at the shores of the lakes a reach can lie in, and 05b_flow.py reads the same outlines for
  # the reaches lying in a lake (flowlib.lake_water; 2026-11-21). 05d_lakes.py needs nothing of the reaches' (each
  # lake's drainage label is looked up when the map is drawn, maplakes.py); 08_hike.py reads the outlines too.
  # It downloads (agency lake lists, GBIF, PAD-US, OSM, lidar): if that fails, the last lakes.gpkg stays
  # then the surveyed depths and contours (lake_bathymetry.py), which 05d_lakes.py leaves out
  if run $a "" 05d_lakes; then
    run $a "" lake_bathymetry || echo "NOTE $a: lake depth surveys not read; lakes.gpkg has no surveyed depths" >> $LOG
  else
    echo "NOTE $a: lakes not rebuilt; the last lakes.gpkg stays" >> $LOG
  fi
  for r in $ranges; do run $a $r 05_score || return 1; done
  # late-summer greenness of the channels (Sentinel-2), which 05b_flow.py reads for creeks the flow model rates flowing
  # that are dry; only for areas with the late_summer_green source (it says so and does nothing elsewhere); kept once made
  run $a "" 02g_greenness || return 1
  # every range's drainages before any range's flow: 05b_flow.py follows a creek whose way leaves its box into the
  # box it runs into and matches it there with that box's area_streams.csv (05c), so a neighbour whose 05c hadn't
  # rerun yet was read on its own box's areas (05b prints a NOTE then)
  for r in $ranges; do run $a $r 05c_drainages || return 1; done
  for r in $ranges; do run $a $r 05b_flow || return 1; done
  run $a "" 02d_trails || return 1
  run $a "" 02e_access || return 1
  # the area's long-distance trail, where config.py lists one (the script stops by itself where there is none)
  AREA=$a $PY -c "import config, sys; sys.exit(0 if config.LONG_TRAIL else 1)" && { run $a "" 02c_pct || return 1; }
  return 0
}

failed=0
for a in "$@"; do
  LOG=../data/mid_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  if steps $a; then echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG; else failed=1; fi
done
exit $failed
