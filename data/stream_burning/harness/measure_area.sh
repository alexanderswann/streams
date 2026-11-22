#!/bin/zsh
# measure_area.sh <root> <outdir for live checks> <area> [area ...]: for each area, a scratch build from 03b (the
# root's patched scripts; the live 03 outputs linked in, since 03 doesn't change), all checks on it and on the live
# build, and the comparison against the live build (compare_roots, moved, straight, falls). Stops an area at its first
# failure and goes on to the next.
R=$1; L=$2; shift 2
H=${0:A:h}; C=$H/../checks; P=/Users/mac/Fishing; PY=$P/.venv/bin/python
export NUMBA_CACHE_DIR=$R/numba BURN_M=0
mkdir -p $L
for a in "$@"; do
  echo "== $a $(date +%H:%M:%S)"
  [[ -d $R/data/raw/$a ]] || $H/setup_root.sh $R $a >/dev/null || { echo "FAILED setup $a"; continue; }
  for d in $P/data/derived/$a/*(/); do
    b=${d:t}; [[ $b == _shared ]] && continue
    mkdir -p $R/data/derived/$a/$b
    for f in dem_cond dem_filled fill_depth; do ln -sf $d/$f.tif $R/data/derived/$a/$b/$f.tif; done
  done
  rm -f $R/data/chain_$a.log
  $H/run_chain.sh $R $a 03b || { echo "FAILED chain $a"; continue; }
  $H/run_checks.sh $R $a >/dev/null 2>&1
  ( cd $P/scripts && {
    echo "#### standing"; AREA=$a $PY -W ignore $C/standing.py -
    echo "#### short_named"; AREA=$a $PY -W ignore $C/short_named.py
    echo "#### v2_ends"; AREA=$a $PY -W ignore $C/v2_ends.py - $L/v2ends_$a.csv
    echo "#### hragree"; AREA=$a $PY -W ignore $C/hragree.py - $L/hr_$a.csv
    echo "#### lake_outlets"; AREA=$a $PY -W ignore $C/lake_outlets.py project
    echo "#### check_flow_drops"; AREA=$a $PY -W ignore ../data/check_flow_drops.py
    echo "#### validate"; AREA=$a $PY -W ignore ../data/validate.py
  } > $L/checks_$a.txt 2>&1 )
  ( cd $R/scripts && {
    AREA=$a $PY -W ignore $C/compare_roots.py $P $R $R/data/compare_$a.csv
    AREA=$a $PY -W ignore $C/moved.py $P $R
    for X in $P $R; do AREA=$a $PY -W ignore $C/straight.py $X; AREA=$a $PY -W ignore $C/falls.py $X; done
  } > $R/data/compare_$a.txt 2>&1 )
  echo "== done $a $(date +%H:%M:%S)"
done
