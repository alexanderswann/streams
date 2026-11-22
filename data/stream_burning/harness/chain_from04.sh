#!/bin/zsh
# chain_from04.sh <root> <first step: 04, 05 or 05b> <area> [area ...]: in a scratch root (setup_clone.sh), per area:
# 04 + 04b per box (first=04), 05_score per box, 05c per box (first=04 or 05), 05b per box; one step after another;
# an area stops at its first failure and the next area goes on. Log: <root>/data/chain_<area>.log
R=$1; first=$2; shift 2
cd $R/scripts
PY=/Users/mac/Fishing/.venv/bin/python
export NUMBA_CACHE_DIR=$R/numba
for a in "$@"; do
  LOG=$R/data/chain_$a.log
  ranges=($(AREA=$a $PY -c "import config; print(' '.join(config.REGIONS))"))
  step() {
    echo "== $a/$1 $2 $(date +%H:%M:%S)" >> $LOG
    AREA=$a REGION=$1 nice -n 10 $PY -W ignore $2.py >> $LOG 2>&1 || { echo "FAILED $a/$1 $2 $(date +%H:%M:%S)" >> $LOG; return 1; }
  }
  area() {
    if [[ $first == 04 ]]; then for r in $ranges; do step $r 04_knickpoints || return 1; step $r 04b_bigcreek_steps || return 1; done; fi
    if [[ $first != 05b ]]; then
      for r in $ranges; do step $r 05_score || return 1; done
      for r in $ranges; do step $r 05c_drainages || return 1; done
    fi
    for r in $ranges; do step $r 05b_flow || return 1; done
  }
  echo "== START $a $(date '+%m-%d %H:%M:%S') root $R first $first" >> $LOG
  area && echo "== DONE $a $(date '+%m-%d %H:%M:%S')" >> $LOG
done
