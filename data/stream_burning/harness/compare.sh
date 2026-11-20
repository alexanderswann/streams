#!/bin/zsh
# compare.sh <rootA> <rootB> <area>: build B against build A (both after run_chain.sh and run_checks.sh), into
# <rootB>/data/compare_<area>.txt: reach-by-reach moves in drainage, flow class and fish score (compare_roots.py), how far
# the drawn lines moved (moved.py), straight flat-resolution runs (straight.py) and drops against known falls (falls.py)
# for both builds.
A=$1; B=$2; a=$3
C=${0:A:h}/../checks
PY=/Users/mac/Fishing/.venv/bin/python
export NUMBA_CACHE_DIR=$B/numba
OUT=$B/data/compare_$a.txt
cd $B/scripts
{
  AREA=$a $PY -W ignore $C/compare_roots.py $A $B $B/data/compare_$a.csv
  AREA=$a $PY -W ignore $C/moved.py $A $B
  for R in $A $B; do
    AREA=$a $PY -W ignore $C/straight.py $R
    AREA=$a $PY -W ignore $C/falls.py $R
  done
} > $OUT 2>&1
echo "comparison written to $OUT"
