#!/bin/zsh
# A scratch copy of the pipeline: setup_root.sh <root> <area> [area ...]
# scripts/ copied (and patched for the burn), data/raw/_national linked, each box's raw files linked one by one (new
# files land in scratch), the area's _shared copied (its cache/ linked file by file), data/ checks copied.
# derived/ and output/ start empty. Nothing under /Users/mac/Fishing is written.
# Put <root> outside the repo (a root holds 0.5-1.5 GB per area once built), e.g. /private/tmp/burn/r0.
set -e
R=$1; shift
P=/Users/mac/Fishing
H=${0:A:h}
mkdir -p $R/data/raw $R/data/derived $R/output
if [[ ! -d $R/scripts ]]; then
  rsync -a --exclude __pycache__ $P/scripts/ $R/scripts/
  cp $H/burnlib.py $R/scripts/
  /Users/mac/Fishing/.venv/bin/python $H/patch_burn.py $R/scripts
  cp $P/data/check_flow_drops.py $P/data/validate.py $R/data/
fi
[[ -e $R/data/raw/_national ]] || ln -s $P/data/raw/_national $R/data/raw/_national
for a in "$@"; do
  for d in $P/data/raw/$a/*(/); do
    b=${d:t}
    if [[ $b == _shared ]]; then
      mkdir -p $R/data/raw/$a/_shared
      rsync -a --exclude cache $d/ $R/data/raw/$a/_shared/
      mkdir -p $R/data/raw/$a/_shared/cache
      for f in $d/cache/*(N); do ln -sf $f $R/data/raw/$a/_shared/cache/${f:t}; done
    else
      mkdir -p $R/data/raw/$a/$b
      for f in $d/*(N.); do ln -sf $f $R/data/raw/$a/$b/${f:t}; done
    fi
  done
  mkdir -p $R/data/derived/$a $R/output/$a
done
echo "root $R ready for $*"
