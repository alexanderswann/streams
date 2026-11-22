#!/bin/zsh
# run_chain.sh <root> <area> <first step: 03, 03b or 04>   (BURN_M / BURN_SLOPE / BURN_EDGE_M from the environment;
# burnlib.py: BURN_M=0 is no burn)
# 03 per box (one at a time), 03b, 04 + 04b per box, 05_score per box, 05c per box, 05b per box; stops at a failure.
# A baseline root can skip 03: copy the project's dem_cond / dem_filled / fill_depth into <root>/data/derived/<area>/<box>/
# and start at 03b (03_hydrology.py unchanged since they were made).
R=$1; a=$2; first=$3
cd $R/scripts
PY=/Users/mac/Fishing/.venv/bin/python
export NUMBA_CACHE_DIR=$R/numba
LOG=$R/data/chain_$a.log
ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
step() {   # step <range or ""> <script>
  echo "== $a/${1:-all} $2 $(date +%H:%M:%S) BURN_M=$BURN_M BURN_SLOPE=$BURN_SLOPE" >> $LOG
  if [[ -n $1 ]]; then AREA=$a REGION=$1 /usr/bin/time -l $PY -W ignore $2.py >> $LOG 2>&1; else AREA=$a /usr/bin/time -l $PY -W ignore $2.py >> $LOG 2>&1; fi \
    || { echo "FAILED $a/${1:-all} $2 $(date +%H:%M:%S)" >> $LOG; exit 1; }
}
echo "== START $a $(date '+%m-%d %H:%M:%S') root $R" >> $LOG
# BOXES (optional): the boxes to condition (03) this time, to resume a chain that stopped part way through 03
if [[ $first == 03 ]]; then for r in ${=BOXES:-$ranges}; do step $r 03_hydrology; done; fi
# first = 03, 03b, 04 (resume after a finished 03b) or 05b (only the flow step, e.g. after the lakes layer came in)
if [[ $first != 05b ]]; then
  [[ $first == 04 ]] || step "" 03b_stitch
  for r in $ranges; do step $r 04_knickpoints; step $r 04b_bigcreek_steps; done
  for r in $ranges; do step $r 05_score; done
  for r in $ranges; do step $r 05c_drainages; done
fi
for r in $ranges; do step $r 05b_flow; done
echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
