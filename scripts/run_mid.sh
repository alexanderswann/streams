#!/bin/zsh
# Middle steps for one or more areas, after run_base.sh: reach scoring, flow, drainages, trails and access roads.
#   ./run_mid.sh ne_ct lexington_va        (logs to data/mid_<area>.log)
# Stops an area at its first failure (later steps need the earlier ones) and goes on to the next area.
cd /Users/mac/Fishing/scripts
PY=../.venv/bin/python

run() {   # run <area> <range or ""> <script>
  echo "== $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG
  if [[ -n $2 ]]; then AREA=$1 REGION=$2 $PY $3.py >> $LOG 2>&1; else AREA=$1 $PY $3.py >> $LOG 2>&1; fi \
    || { echo "FAILED $1/${2:-all} $3 $(date +%H:%M:%S)" >> $LOG; return 1; }
}

steps() {
  local a=$1 r
  local ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  for r in $ranges; do run $a $r 05_score || return 1; done
  run $a "" 02b_download_flow || return 1
  for r in $ranges; do run $a $r 05c_drainages || return 1; run $a $r 05b_flow || return 1; done
  run $a "" 02d_trails || return 1
  run $a "" 02e_access || return 1
  # the area's long-distance trail, where config.py lists one (the script stops by itself where there is none)
  AREA=$a $PY -c "import config, sys; sys.exit(0 if config.LONG_TRAIL else 1)" && { run $a "" 02c_pct || return 1; }
  return 0
}

for a in "$@"; do
  LOG=../data/mid_$a.log
  echo "== START $a $(date '+%m-%d %H:%M:%S')" >> $LOG
  steps $a && echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
done
