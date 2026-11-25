#!/bin/zsh
# One area, built with one command (the new-area plan's B9, 2026-11-23):
#   ./run_area.sh <area> [from-step]        ./run_area.sh ne_ct        ./run_area.sh ne_ct 05b_flow
# runs run_base.sh, run_mid.sh and run_late.sh in turn for the area (their logs as always: data/base_<area>.log,
# data/mid_<area>.log, data/late_<area>.log), from the step named on (FROM: the steps before it keep what they made;
# `python build_stamp.py steps` lists them in order). Then the build check on the area's new map,
# audit/scripts/check_build.sh (the same check a hand-off between sessions runs: the code is the committed tree, the
# standing audit tables with completeness, the golden places, and lines, drainage, scores and lake outlets against the
# live map), into audit/tables/build_<area>/: its PREHANDOFF.md, and the run_all_status.json the publish gate reads. It
# ends with one line per part (OK, or what failed) and the build stamp (build_stamp.py show). Exit status 0 only when
# every step ran and the check passed.
#   CHECKS=quick ./run_area.sh ...  the check without its 17-minute audit tables (the publish gate then refuses the map)
#   CHECKS=0 ./run_area.sh ...      no check at all (a test run)
# The build takes one build slot (buildslot.sh: at most 2 heavy builds at once on this Mac, project builds first) and
# its three drivers run in it; the slot goes when the last driver ends, before the check, which reads and doesn't build.
# The drivers keep their names, so publish_site.sh's guard sees a build running. Run from a scratch copy of the project
# by its full path, it builds in that copy: the drivers are called by their full paths, which the guard counts as a
# scratch run.
# Afterwards, for the site: 13_overview.py, 14_portable.py and phone_sync.sh (publish_site.sh push runs them).
here=${0:a:h}
cd $here
PY=../.venv/bin/python
area=$1; from=$2
[[ -z $area || $# -gt 2 ]] && { echo "usage: run_area.sh <area> [from-step]"; exit 2; }
AREA=$area AREA_SETUP=1 $PY -c "import config" || exit 2          # an area config.py (or AREAS_FILE) has
if [[ -n $from ]]; then
  steps=($($PY build_stamp.py steps))
  (( ${steps[(Ie)$from]} )) || { echo "run_area.sh: no step $from; the steps, in order: $steps"; exit 2; }
fi
source ./buildslot.sh      # one slot for the build: run_base, run_mid and run_late run in it (BUILDSLOT_HELD)
buildslot_acquire "${0:t} $*"
export FROM=$from FROM_REACHED=${TMPDIR:-/tmp}/run_area_$$_reached
rm -f $FROM_REACHED
trap 'rm -f $FROM_REACHED; _bs_exit' EXIT      # buildslot.sh's EXIT trap, which this one replaces, lets the slot go
t0=$(date +%s)
stopped=""
for d in base mid late; do
  echo "== run_area $area: run_$d.sh${from:+ (from $from)} $(date +%H:%M:%S)"
  $here/run_$d.sh $area || { stopped=$d; break; }
done
buildslot_release          # the build is over: the next one may start while this one is checked
mins=$(( ($(date +%s) - t0 + 59) / 60 ))
if [[ -n $stopped ]]; then
  echo "steps: FAILED in run_$stopped.sh after $mins min (data/${stopped}_$area.log: $(grep -E '^FAILED' ../data/${stopped}_$area.log | tail -1))"
  $PY build_stamp.py show $area | tail -5
  exit 1
fi
[[ -n $from && ! -e $FROM_REACHED ]] && { echo "steps: FROM=$from was never reached; nothing ran"; exit 1; }
echo "steps: OK in $mins min${from:+ (from $from)}"
checks=0
if [[ ${CHECKS:-1} != 0 ]]; then
  if [[ -x ../audit/scripts/check_build.sh ]]; then
    QUICK=$([[ $CHECKS == quick ]] && echo 1) AREAS=$area ../audit/scripts/check_build.sh build_$area ${here:h} \
      > ../data/checks_$area.log 2>&1
    checks=$?
    st=../audit/tables/build_$area/run_all_status.json
    bad=$([[ -f $st && $CHECKS != quick ]] && $PY -c "import json, sys; d = json.load(open(sys.argv[1])); print('; '.join(d.get('failed', []) + ['golden: ' + g for g in d.get('golden', {}).get('failed', [])]))" $st)
    if (( checks == 0 )) && [[ -z $bad ]]; then
      echo "checks: OK$([[ $CHECKS == quick ]] && echo ' (quick: no audit tables, so not yet publishable)') (audit/tables/build_$area/PREHANDOFF.md)"
    else
      echo "checks: FAILED: $(grep -h -E '^- FAIL|^\*\*FAIL' ../audit/tables/build_$area/PREHANDOFF.md | head -3 | tr '\n' ' ')${bad:+$bad }(data/checks_$area.log)"
      checks=1
    fi
  else
    echo "checks: FAILED: no audit/scripts/check_build.sh in this copy"; checks=1
  fi
else
  echo "checks: left out (CHECKS=0)"
fi
$PY build_stamp.py show $area | awk '{ n++ } /failed|uncommitted|edited during/ { bad = bad "\n  " $0 } END { print "stamp: " n " step runs recorded" (bad ? ", these with a flag:" bad : ", none failed or on uncommitted code") }'
exit $checks
