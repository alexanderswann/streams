#!/bin/zsh
# evaluate.sh <rootA> <rootB> <outdir> <area> [area ...]: fish scores for both scratch roots (checks/score_root.py:
# the late values by place, from the project or from LATE_ROOT, a frozen root, while the project is being rebuilt),
# the checks on each, and the comparison of B against A.
# Results: <outdir>/<area>.txt, compare_<area>.csv, straddle_<root>_<area>.csv, v2ends_<root>_<area>.csv;
# checks/sumeval.py <outdir> makes the table over the areas, checks/moves2.py the moves by what each reach is.
C=${0:A:h}/../checks
PY=/Users/mac/Fishing/.venv/bin/python
A=$1; B=$2; E=$3; shift 3
mkdir -p $E
for a in "$@"; do
  {
    for R in $A $B; do
      export NUMBA_CACHE_DIR=$R/numba
      echo "######## ${R:t}"
      cd $R/scripts
      echo "#### score_root"; AREA=$a $PY -W ignore $C/score_root.py $R
      echo "#### standing"; AREA=$a $PY -W ignore $C/standing.py $R
      echo "#### lake_outlets"; ROOT=$R AREA=$a $PY -W ignore $C/lake_outlets.py project
      echo "#### check_flow_drops"; AREA=$a $PY -W ignore $R/data/check_flow_drops.py
      echo "#### validate"; AREA=$a $PY -W ignore $R/data/validate.py
      echo "#### falls"; AREA=$a $PY -W ignore $C/falls.py $R
      echo "#### straddle"; AREA=$a $PY -W ignore $C/lake_shares.py $R $E/straddle_${R:t}_$a.csv
      echo "#### v2_ends"; AREA=$a $PY -W ignore $C/v2_ends.py $R $E/v2ends_${R:t}_$a.csv 2>&1 | tail -4
      echo "#### piece_water"; AREA=$a $PY -W ignore $C/piece_water.py $R 2>&1 | tail -1
    done
    echo "######## compare ${B:t} against ${A:t}"
    cd $B/scripts
    AREA=$a $PY -W ignore $C/compare_roots.py $A $B $E/compare_$a.csv
    AREA=$a $PY -W ignore $C/moved.py $A $B
  } > $E/$a.txt 2>&1
  echo "$a: $(grep -c Traceback $E/$a.txt) tracebacks"
done
