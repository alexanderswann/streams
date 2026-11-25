#!/bin/zsh
# The new-area test (the new-area plan's section 6 and 12.1; B9, 2026-11-23): build a place the pipeline has never
# seen, from nothing, in a scratch copy of the project, with one command and no edit; then check it and write a report.
#   scripts/new_area_test.sh <area> <scratch folder> [areas file]
#   e.g.  scripts/new_area_test.sh fryingpan /private/tmp/claude-501/<...>/scratchpad/newarea
# <area> is an entry of the areas file (default: tests/new_areas.json, as committed: label, home, outline, hidden and
# nothing else; config.py reads it through AREAS_FILE, so no file of the pipeline is edited).
# The copy, <scratch folder>/<area>/: the code as committed (the project's HEAD; uncommitted changes are not tested),
# empty data/raw/<area>, data/derived/<area> and output/<area>, and the national downloads (NHD, PRISM, GNIS, the state
# outlines) as APFS clones of the project's, so a new download lands in the copy and nothing of the project is written.
# The build is the copy's run_area.sh, called by its full path: publish_site.sh's guard counts it as a scratch run.
# Report: <scratch folder>/<area>_report.md: the steps and their times, the sources left out and why, the build check,
# words of other maps left in the page, the build stamp, the time and disk the build took. Exit status: run_area.sh's.
# Afterwards the copy's data/raw/<area> and data/derived/<area> are deleted (KEEP=1 keeps them); output/ and the logs stay.
# The overview session's rules (2026-11-22): never while a project rebuild or more than one other scratch chain runs; the
# five-place suite at most once a week, overnight, one area at a time. It stops if a project build is running (FORCE=1
# goes on anyway). DRYRUN=1 sets up the copy and stops before the build.
P=${0:a:h:h}
area=$1; base=$2; areas=${3:-}
[[ -z $area || -z $base ]] && { echo "usage: new_area_test.sh <area> <scratch folder> [areas file]"; exit 2; }
[[ $base == $P || $base == $P/* ]] && { echo "the scratch folder must be outside the project"; exit 2; }
if [[ -z $FORCE ]]; then
  busy=$(pgrep -fl "(^| )(\./|$P/scripts/)run_[a-z_0-9]+\.sh" | head -1)
  [[ -n $busy ]] && { echo "a project build is running ($busy): not now (FORCE=1 to go on)"; exit 3; }
fi
W=$base/$area
mkdir -p $base || exit 2
[[ -e $W ]] && { echo "$W exists: remove it first (rm -rf $W) or pick another scratch folder"; exit 2; }
head=$(git -C $P rev-parse HEAD) || exit 2
git clone -q $P $W && git -C $W checkout -q --detach $head || exit 2
dirty=$(git -C $P status --porcelain -- scripts tests | head -5)
ln -s $P/.venv $W/.venv
mkdir -p $W/data/raw $W/data/derived $W/output
if [[ $(stat -f %d $P/data/raw/_national) == $(stat -f %d $W/data/raw) ]]; then
  cp -Rc $P/data/raw/_national $W/data/raw/ || exit 2       # clones: no space used, and no write reaches the project
else
  echo "the scratch folder is on another disk: the national downloads would be copied in full; use a scratchpad folder"
  exit 2
fi
areas=${areas:-$W/tests/new_areas.json}
[[ -f $areas ]] || { echo "no areas file $areas"; exit 2; }
export AREAS_FILE=${areas:a}
AREA=$area AREA_SETUP=1 $W/.venv/bin/python -c "import sys; sys.path.insert(0, '$W/scripts'); import config" || exit 2
R=$base/${area}_report.md
echo "copy ready: $W (code $head${dirty:+; the project has uncommitted changes, not tested})"
if [[ -n $DRYRUN ]]; then
  echo "DRYRUN: would run  AREAS_FILE=$AREAS_FILE nice -n 10 $W/scripts/run_area.sh $area"
  exit 0
fi
t0=$(date +%s); touch $W/.started
nice -n 10 $W/scripts/run_area.sh $area > $W/run_area.log 2>&1
rc=$?
t1=$(date +%s)
{
  echo "# New-area test: $area ($(date '+%Y-%m-%d %H:%M'))"
  echo
  echo "- Code: $head${dirty:+ (the project had uncommitted changes, which were not tested)}"
  echo "- Entry: $($W/.venv/bin/python -c "import json, sys; print(json.dumps(json.load(open(sys.argv[1]))[sys.argv[2]]))" $AREAS_FILE $area)"
  echo "- Result: $( (( rc == 0 )) && echo 'every step ran and every check passed' || echo "run_area.sh exit $rc")"
  echo "- Time: $(( (t1 - t0 + 59) / 60 )) min. Disk: $(du -sh $W/data/raw/$area $W/data/derived/$area $W/output/$area 2>/dev/null | awk '{printf "%s %s; ", $1, $2}' | sed "s|$W/||g")"
  echo "- New national downloads: $(find $W/data/raw/_national -type f -newer $W/.started | wc -l | tr -d ' ') files, $(find $W/data/raw/_national -type f -newer $W/.started -print0 | xargs -0 du -ch 2>/dev/null | tail -1 | cut -f1) (kept only in the copy)"
  echo
  echo "## run_area.sh"
  echo '```'
  cat $W/run_area.log
  echo '```'
  echo
  echo "## The area's settings (00_area.py) and what was left out"
  echo '```'
  sed -n '/00_area/,/== /p' $W/data/base_$area.log 2>/dev/null | grep -v '^==' | head -20
  grep -h -E '^(NOTE|RETRY|FAILED|== STOPPED)|NOTE ' $W/data/{base,mid,late}_$area.log 2>/dev/null | sort | uniq -c | sort -rn | head -40
  echo '```'
  echo
  echo "## Words of other maps left in the page (each should be 0)"
  for w in "CA State Parks" "PCT" "Pacific Crest" "Santa Monica" "LA County"; do
    echo "- \"$w\": $(cat $W/output/$area/{stream_map.html,stream_map_3d.html,map3d_data.js} 2>/dev/null | grep -o "$w" | wc -l | tr -d ' ')"
  done
  echo
  echo "## The build check (audit/scripts/check_build.sh)"
  cat $W/audit/tables/build_$area/PREHANDOFF.md 2>/dev/null || echo "(no check summary: see $W/data/checks_$area.log)"
  echo
  echo "## Build stamp"
  echo '```'
  (cd $W/scripts && ../.venv/bin/python build_stamp.py show $area)
  echo '```'
} > $R
echo "report: $R"
if [[ -z $KEEP ]]; then
  rm -rf $W/data/raw/$area $W/data/derived/$area
  echo "deleted the copy's data for $area (KEEP=1 keeps it); its maps stay in $W/output/$area"
fi
exit $rc
