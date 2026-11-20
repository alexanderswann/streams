#!/bin/zsh
# run_checks.sh <root> <area>: every check on one build (after run_chain.sh), into <root>/data/checks_<area>.txt
# (score_root.py first: it gives the root's reaches their fish scores and writes the ranked table the others read)
R=$1; a=$2
C=${0:A:h}/../checks
PY=/Users/mac/Fishing/.venv/bin/python
export NUMBA_CACHE_DIR=$R/numba
OUT=$R/data/checks_$a.txt
cd $R/scripts
{
  echo "#### score_root"; AREA=$a $PY -W ignore $C/score_root.py $R
  echo "#### standing"; AREA=$a $PY -W ignore $C/standing.py $R
  echo "#### short_named"; ROOT=$R AREA=$a $PY -W ignore $C/short_named.py
  echo "#### classify_short"; OUTDIR=$R/data AREA=$a $PY -W ignore $C/classify_short.py $R
  echo "#### v2_ends"; AREA=$a $PY -W ignore $C/v2_ends.py $R $R/data/v2ends_$a.csv
  echo "#### hragree"; AREA=$a $PY -W ignore $C/hragree.py $R $R/data/hr_$a.csv
  echo "#### lake_outlets"; ROOT=$R AREA=$a $PY -W ignore $C/lake_outlets.py project
  echo "#### check_flow_drops"; AREA=$a $PY -W ignore $R/data/check_flow_drops.py
  echo "#### validate"; AREA=$a $PY -W ignore $R/data/validate.py
} > $OUT 2>&1
echo "checks written to $OUT"
