#!/bin/zsh
# remeasure_05b.sh <root> <live checks dir> <area> [area ...]: rerun only 05b in a measured root (after an input of
# 05b's changed, e.g. the lakes layer copied in), then the root's checks and the comparison, as measure_area.sh does.
R=$1; L=$2; shift 2
H=${0:A:h}; C=$H/../checks; P=/Users/mac/Fishing; PY=$P/.venv/bin/python
export NUMBA_CACHE_DIR=$R/numba BURN_M=0
for a in "$@"; do
  echo "== $a $(date +%H:%M:%S)"
  $H/run_chain.sh $R $a 05b || { echo "FAILED 05b $a"; continue; }
  $H/run_checks.sh $R $a >/dev/null 2>&1
  ( cd $R/scripts && {
    AREA=$a $PY -W ignore $C/compare_roots.py $P $R $R/data/compare_$a.csv
    AREA=$a $PY -W ignore $C/moved.py $P $R
    for X in $P $R; do AREA=$a $PY -W ignore $C/straight.py $X; AREA=$a $PY -W ignore $C/falls.py $X; done
  } > $R/data/compare_$a.txt 2>&1 )
  echo "== done $a $(date +%H:%M:%S)"
done
