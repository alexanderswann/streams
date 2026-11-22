#!/bin/zsh
# A scratch copy of the pipeline from 04 on: setup_clone.sh <root> <derived source root> <area> [area ...]
# (<derived source root>: the project, or a root that holds the 03b outputs to start from)
# scripts/ copied as they are in the project (first time only). Everything else is an APFS clone (cp -c: no space
# used, and a stray write in the scratch root can never reach the original): each box's raw files, the area's raw
# _shared, each box's derived files and the area's derived _shared from <derived source root>/data/derived.
# output/ starts empty. Nothing under /Users/mac/Fishing is written.
set -e
R=$1; D=$2; shift 2
P=/Users/mac/Fishing
mkdir -p $R/data/raw $R/data/derived $R/output
if [[ ! -d $R/scripts ]]; then
  rsync -a --exclude __pycache__ $P/scripts/ $R/scripts/
  cp $P/data/check_flow_drops.py $P/data/validate.py $R/data/
fi
[[ -e $R/data/raw/_national ]] || ln -s $P/data/raw/_national $R/data/raw/_national
for a in "$@"; do
  for d in $P/data/raw/$a/*(/); do
    b=${d:t}
    mkdir -p $R/data/raw/$a/$b
    if [[ $b == _shared ]]; then
      cp -Rc $d/ $R/data/raw/$a/_shared/
    else
      for f in $d/*(N-.); do cp -c $f $R/data/raw/$a/$b/${f:t}; done
    fi
  done
  mkdir -p $R/data/derived/$a/_shared $R/output/$a
  for d in $D/data/derived/$a/*(/); do
    b=${d:t}
    mkdir -p $R/data/derived/$a/$b
    for f in $d/*(N-.); do cp -c $f $R/data/derived/$a/$b/${f:t}; done
  done
done
echo "root $R ready for $*"
